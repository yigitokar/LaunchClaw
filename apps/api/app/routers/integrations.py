import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership

router = APIRouter(tags=["integrations"])

INTEGRATION_RESPONSE_FIELDS = "id, claw_id, provider, status, scope_summary, metadata, created_at, updated_at"
GITHUB_SCOPE_SUMMARY = "repo metadata, pull requests, contents"
STATE_TTL_SECONDS = 600


def _encode_token_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_token_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _state_secret() -> bytes:
    secret_source = (
        settings.supabase_service_key
        or settings.internal_service_token
        or f"{settings.app_name}:{settings.cors_origin}:{settings.github_app_slug}"
    )
    return secret_source.encode("utf-8")


def generate_github_state(claw_id: str) -> str:
    payload = {
        "claw_id": claw_id,
        "exp": int(time.time()) + STATE_TTL_SECONDS,
    }
    encoded_payload = _encode_token_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_state_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_encode_token_bytes(signature)}"


def validate_github_state(state: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = state.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Invalid GitHub state token"},
        ) from exc

    expected_signature = _encode_token_bytes(
        hmac.new(_state_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Invalid GitHub state token"},
        )

    try:
        payload = json.loads(_decode_token_bytes(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Invalid GitHub state token"},
        ) from exc

    if not isinstance(payload, dict) or not payload.get("claw_id"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Invalid GitHub state token"},
        )

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_state", "message": "Expired GitHub state token"},
        )

    return payload


def get_integration_for_claw(claw_id: str, integration_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("integrations")
        .select(INTEGRATION_RESPONSE_FIELDS)
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Integration not found"})
    return result.data


def get_github_integration_for_claw(claw_id: str) -> dict[str, Any] | None:
    result = (
        get_supabase()
        .table("integrations")
        .select(INTEGRATION_RESPONSE_FIELDS)
        .eq("claw_id", claw_id)
        .eq("provider", "github")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    items = result.data or []
    return items[0] if items else None


def ensure_claw_exists(claw_id: str) -> None:
    result = get_supabase().table("claws").select("id").eq("id", claw_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Claw not found"})


@router.get("/api/claws/{claw_id}/integrations")
async def list_integrations(
    claw_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, list[dict[str, Any]]]:
    verify_claw_ownership(claw_id, user_id)

    result = (
        get_supabase()
        .table("integrations")
        .select(INTEGRATION_RESPONSE_FIELDS)
        .eq("claw_id", claw_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": result.data or []}


@router.post("/api/claws/{claw_id}/integrations/github/connect")
async def connect_github_integration(
    claw_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    verify_claw_ownership(claw_id, user_id)
    state = generate_github_state(claw_id)
    redirect_url = f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}"
    return {"redirect_url": redirect_url}


@router.get("/api/integrations/github/callback")
async def github_callback(
    state: str = Query(..., min_length=1),
    installation_id: int | None = Query(None, ge=1),
) -> RedirectResponse:
    if installation_id is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "installation_id is required"},
        )

    payload = validate_github_state(state)
    claw_id = str(payload["claw_id"])
    ensure_claw_exists(claw_id)

    update_payload = {
        "provider": "github",
        "status": "connected",
        "scope_summary": GITHUB_SCOPE_SUMMARY,
        "external_account_ref": str(installation_id),
        "metadata": {"installation_id": installation_id},
    }
    existing = get_github_integration_for_claw(claw_id)

    if existing:
        result = (
            get_supabase()
            .table("integrations")
            .update(update_payload)
            .eq("id", existing["id"])
            .eq("claw_id", claw_id)
            .execute()
        )
        integration = result.data[0]
    else:
        result = (
            get_supabase()
            .table("integrations")
            .insert({"claw_id": claw_id, **update_payload})
            .execute()
        )
        integration = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_connected",
        summary="GitHub integration connected",
        metadata={
            "integration_id": integration["id"],
            "provider": "github",
            "installation_id": installation_id,
            "status": integration["status"],
        },
    )

    workspace_url = f"{settings.cors_origin.rstrip('/')}/workspace/{claw_id}"
    return RedirectResponse(url=workspace_url, status_code=303)


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/disconnect")
async def disconnect_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    get_integration_for_claw(claw_id, integration_id)

    result = (
        get_supabase()
        .table("integrations")
        .update({"status": "disconnected"})
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    return result.data[0]


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/refresh")
async def refresh_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    integration = get_integration_for_claw(claw_id, integration_id)

    result = (
        get_supabase()
        .table("integrations")
        .update({"scope_summary": integration.get("scope_summary") or GITHUB_SCOPE_SUMMARY})
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    return result.data[0]
