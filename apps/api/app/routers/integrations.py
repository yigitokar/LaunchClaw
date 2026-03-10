import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership
from app.services.github_app import get_github_app_installation, require_github_app_credentials
from app.services.scheduler import utc_now

router = APIRouter(tags=["integrations"])

GITHUB_PROVIDER = "github"
GITHUB_SCOPE_SUMMARY = "repo metadata, pull requests, contents"
STATE_TTL_MINUTES = 15
LIST_FIELDS = "id, claw_id, provider, status, external_account_ref, scope_summary, created_at, updated_at"
DETAIL_FIELDS = f"{LIST_FIELDS}, config_json"
PENDING_STATE_TOKEN_KEY = "pending_state_token"
PENDING_STATE_EXPIRES_AT_KEY = "pending_state_expires_at"


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _state_secret() -> bytes:
    secret = settings.github_app_state_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub state signing is not configured"),
        )
    return secret.encode("utf-8")


def _github_install_url(state_token: str) -> str:
    slug = settings.github_app_slug.strip()
    if not slug:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub App slug is not configured"),
        )
    return f"https://github.com/apps/{slug}/installations/new?state={state_token}"


def _workspace_redirect_url(claw_id: str) -> str:
    return f"{settings.cors_origin.rstrip('/')}/workspace/{claw_id}/integrations?github=connected"


def _next_connect_status(current_status: str | None) -> str:
    return current_status if current_status in {"connected", "degraded"} else "pending"


def _encode_state_bytes(raw_value: bytes) -> str:
    return base64.urlsafe_b64encode(raw_value).rstrip(b"=").decode("ascii")


def _decode_state_bytes(encoded_value: str) -> bytes:
    padding = "=" * (-len(encoded_value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{encoded_value}{padding}".encode("ascii"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        ) from exc


def _sign_state(encoded_payload: str) -> str:
    signature = hmac.new(_state_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return _encode_state_bytes(signature)


def _generate_state_token(claw_id: str, integration_id: str) -> tuple[str, str]:
    expires_at = utc_now() + timedelta(minutes=STATE_TTL_MINUTES)
    payload = {
        "claw_id": claw_id,
        "integration_id": integration_id,
        "nonce": secrets.token_urlsafe(16),
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _encode_state_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded_payload}.{_sign_state(encoded_payload)}", expires_at.isoformat()


def _validate_state_token(state_token: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = state_token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        ) from exc

    if not hmac.compare_digest(signature, _sign_state(encoded_payload)):
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        )

    try:
        payload = json.loads(_decode_state_bytes(encoded_payload))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        )

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(utc_now().timestamp()):
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "GitHub state token has expired"),
        )

    return payload


def _serialize_integration(integration: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": integration["id"],
        "claw_id": integration["claw_id"],
        "provider": integration["provider"],
        "status": integration["status"],
        "external_account_ref": integration.get("external_account_ref"),
        "scope_summary": integration.get("scope_summary"),
        "created_at": integration["created_at"],
        "updated_at": integration["updated_at"],
    }


def _get_integration_for_claw(claw_id: str, integration_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("integrations")
        .select(DETAIL_FIELDS)
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Integration not found"))
    return result.data


def _get_latest_github_integration_for_claw(claw_id: str) -> dict[str, Any] | None:
    result = (
        get_supabase()
        .table("integrations")
        .select(DETAIL_FIELDS)
        .eq("claw_id", claw_id)
        .eq("provider", GITHUB_PROVIDER)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    items = result.data or []
    return items[0] if items else None


@router.get("/api/claws/{claw_id}/integrations")
async def list_integrations(
    claw_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, list[dict[str, Any]]]:
    verify_claw_ownership(claw_id, user_id)

    result = (
        get_supabase()
        .table("integrations")
        .select(LIST_FIELDS)
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
    _state_secret()
    require_github_app_credentials()

    integration = _get_latest_github_integration_for_claw(claw_id)
    if integration is None:
        result = (
            get_supabase()
            .table("integrations")
            .insert(
                {
                    "claw_id": claw_id,
                    "provider": GITHUB_PROVIDER,
                    "status": "pending",
                    "scope_summary": GITHUB_SCOPE_SUMMARY,
                    "config_json": {},
                }
            )
            .execute()
        )
        integration = result.data[0]

    state_token, expires_at = _generate_state_token(claw_id, integration["id"])
    config_json = dict(integration.get("config_json") or {})
    config_json[PENDING_STATE_TOKEN_KEY] = state_token
    config_json[PENDING_STATE_EXPIRES_AT_KEY] = expires_at
    config_json["pending_connect_started_at"] = utc_now().isoformat()
    next_status = _next_connect_status(integration.get("status"))

    (
        get_supabase()
        .table("integrations")
        .update(
            {
                "status": next_status,
                "scope_summary": GITHUB_SCOPE_SUMMARY,
                "config_json": config_json,
            }
        )
        .eq("id", integration["id"])
        .eq("claw_id", claw_id)
        .execute()
    )

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_connect_started",
        summary="GitHub connection started",
        metadata={
            "integration_id": integration["id"],
            "provider": GITHUB_PROVIDER,
        },
    )

    return {"redirect_url": _github_install_url(state_token)}


@router.get("/api/integrations/github/callback")
async def github_callback(
    state: str | None = Query(None),
    installation_id: str | None = Query(None),
    setup_action: str | None = Query(None),
) -> RedirectResponse:
    _state_secret()

    if not state or not installation_id:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Missing required GitHub callback parameters"),
        )

    payload = _validate_state_token(state)
    claw_id = payload.get("claw_id")
    integration_id = payload.get("integration_id")
    if not isinstance(claw_id, str) or not claw_id or not isinstance(integration_id, str) or not integration_id:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Invalid GitHub state token"),
        )

    integration = _get_integration_for_claw(claw_id, integration_id)
    config_json = dict(integration.get("config_json") or {})
    if config_json.get(PENDING_STATE_TOKEN_KEY) != state:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "GitHub state token does not match the active install flow"),
        )

    installation = get_github_app_installation(installation_id)
    account = installation.get("account") if isinstance(installation, dict) else None

    config_json.pop(PENDING_STATE_TOKEN_KEY, None)
    config_json.pop(PENDING_STATE_EXPIRES_AT_KEY, None)
    config_json.pop("pending_connect_started_at", None)
    config_json["installation_id"] = installation_id
    config_json["last_connected_at"] = utc_now().isoformat()
    config_json["repository_selection"] = installation.get("repository_selection")
    config_json["permissions"] = installation.get("permissions")
    config_json["target_type"] = installation.get("target_type")
    if isinstance(account, dict):
        config_json["account_login"] = account.get("login")
        config_json["account_type"] = account.get("type")
    if setup_action:
        config_json["setup_action"] = setup_action

    result = (
        get_supabase()
        .table("integrations")
        .update(
            {
                "status": "connected",
                "external_account_ref": installation_id,
                "scope_summary": GITHUB_SCOPE_SUMMARY,
                "config_json": config_json,
            }
        )
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    updated = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_connected",
        summary="GitHub connected",
        metadata={
            "integration_id": integration_id,
            "provider": GITHUB_PROVIDER,
            "installation_id": installation_id,
            "account_login": config_json.get("account_login"),
            "status": updated["status"],
        },
    )

    return RedirectResponse(url=_workspace_redirect_url(claw_id), status_code=303)


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/disconnect")
async def disconnect_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    integration = _get_integration_for_claw(claw_id, integration_id)

    config_json = dict(integration.get("config_json") or {})
    config_json.pop(PENDING_STATE_TOKEN_KEY, None)
    config_json.pop(PENDING_STATE_EXPIRES_AT_KEY, None)
    config_json["last_disconnected_at"] = utc_now().isoformat()

    result = (
        get_supabase()
        .table("integrations")
        .update({"status": "disconnected", "config_json": config_json})
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    updated = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_disconnected",
        summary="GitHub disconnected",
        metadata={
            "integration_id": integration_id,
            "provider": integration["provider"],
            "previous_status": integration["status"],
            "status": updated["status"],
        },
    )

    return _serialize_integration(updated)


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/refresh")
async def refresh_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    integration = _get_integration_for_claw(claw_id, integration_id)

    config_json = dict(integration.get("config_json") or {})
    config_json["last_refreshed_at"] = utc_now().isoformat()

    result = (
        get_supabase()
        .table("integrations")
        .update({"config_json": config_json})
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    updated = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_refreshed",
        summary="GitHub integration refreshed",
        metadata={
            "integration_id": integration_id,
            "provider": integration["provider"],
            "status": updated["status"],
        },
    )

    return _serialize_integration(updated)
