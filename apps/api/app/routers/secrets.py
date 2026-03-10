from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership
from app.services.scheduler import utc_now

router = APIRouter(prefix="/api/claws/{claw_id}/secrets", tags=["secrets"])

SECRET_RESPONSE_FIELDS = "id, claw_id, provider, label, status, last_rotated_at, restart_required, created_at"
SECRET_DETAIL_FIELDS = f"{SECRET_RESPONSE_FIELDS}, encrypted_value"


class UpsertSecretRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1)


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Provider is required"),
        )
    return normalized


def _normalize_label(label: str) -> str:
    normalized = label.strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Label is required"),
        )
    return normalized


def _validate_value(value: str) -> str:
    if not value.strip():
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "Secret value is required"),
        )
    return value


def _serialize_secret(secret: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": secret["id"],
        "claw_id": secret["claw_id"],
        "provider": secret["provider"],
        "label": secret["label"],
        "status": secret["status"],
        "last_rotated_at": secret.get("last_rotated_at"),
        "restart_required": bool(secret.get("restart_required", False)),
        "created_at": secret["created_at"],
    }


def _restart_required_for_claw(status: str) -> bool:
    return status not in {"creating", "provisioning", "deleted"}


def _get_secret_for_claw(claw_id: str, secret_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("secrets")
        .select(SECRET_DETAIL_FIELDS)
        .eq("id", secret_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Secret not found"))
    return result.data


@router.get("")
async def list_secrets(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, list[dict[str, Any]]]:
    verify_claw_ownership(claw_id, user_id)

    result = (
        get_supabase()
        .table("secrets")
        .select(SECRET_RESPONSE_FIELDS)
        .eq("claw_id", claw_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": [_serialize_secret(secret) for secret in (result.data or [])]}


@router.post("")
async def upsert_secret(
    claw_id: str,
    body: UpsertSecretRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    claw = verify_claw_ownership(claw_id, user_id)

    provider = _normalize_provider(body.provider)
    label = _normalize_label(body.label)
    encrypted_value = _validate_value(body.value)
    now_iso = utc_now().isoformat()
    restart_required = _restart_required_for_claw(claw["status"])

    existing = (
        get_supabase()
        .table("secrets")
        .select(SECRET_DETAIL_FIELDS)
        .eq("claw_id", claw_id)
        .eq("label", label)
        .maybe_single()
        .execute()
    )

    payload = {
        "provider": provider,
        "label": label,
        "encrypted_value": encrypted_value,
        "status": "active",
        "last_rotated_at": now_iso,
        "restart_required": restart_required,
    }

    if existing.data:
        result = (
            get_supabase()
            .table("secrets")
            .update(payload)
            .eq("id", existing.data["id"])
            .eq("claw_id", claw_id)
            .execute()
        )
    else:
        result = (
            get_supabase()
            .table("secrets")
            .insert({"id": f"secret_{uuid4().hex[:12]}", "claw_id": claw_id, **payload})
            .execute()
        )

    secret = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="secret_rotated",
        summary=f"Secret rotated: {label}",
        metadata={
            "secret_id": secret["id"],
            "provider": provider,
            "label": label,
            "restart_required": restart_required,
        },
    )

    return _serialize_secret(secret)


@router.delete("/{secret_id}")
async def revoke_secret(
    claw_id: str,
    secret_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    claw = verify_claw_ownership(claw_id, user_id)
    existing = _get_secret_for_claw(claw_id, secret_id)

    if existing["status"] == "revoked":
        return _serialize_secret(existing)

    restart_required = _restart_required_for_claw(claw["status"])
    result = (
        get_supabase()
        .table("secrets")
        .update({"status": "revoked", "restart_required": restart_required})
        .eq("id", secret_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    return _serialize_secret(result.data[0])
