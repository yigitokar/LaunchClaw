from datetime import datetime, timezone
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership


router = APIRouter(prefix="/api/claws", tags=["lifecycle"])

VALID_TRANSITIONS: Final[dict[str, set[str]]] = {
    "creating": {"provisioning"},
    "provisioning": {"healthy", "failed"},
    "healthy": {"paused", "restarting", "degraded"},
    "paused": {"healthy"},
    "restarting": {"healthy"},
    "degraded": {"restarting"},
    "failed": {"provisioning"},
}


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _raise_invalid_transition(current_status: str, target_status: str) -> None:
    allowed = sorted(VALID_TRANSITIONS.get(current_status, set()))
    message = f"Cannot transition claw from {current_status} to {target_status}."
    if allowed:
        message = f"{message} Allowed transitions: {', '.join(allowed)}."
    raise HTTPException(status_code=409, detail=_detail("conflict", message))


def _ensure_transition(current_status: str, target_status: str) -> None:
    if target_status not in VALID_TRANSITIONS.get(current_status, set()):
        _raise_invalid_transition(current_status, target_status)


def _persist_claw_status(
    *,
    claw_id: str,
    user_id: str,
    current_status: str,
    target_status: str,
) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("claws")
        .update(
            {
                "status": target_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .eq("status", current_status)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=409,
            detail=_detail("conflict", "Claw status changed before this action completed. Refresh and try again."),
        )

    return result.data[0]


def _transition_claw(
    *,
    claw_id: str,
    user_id: str,
    target_status: str,
    event_type: str,
    summary: str,
    action: str,
) -> dict[str, Any]:
    claw = verify_claw_ownership(claw_id, user_id)
    _ensure_transition(claw["status"], target_status)

    updated = _persist_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        current_status=claw["status"],
        target_status=target_status,
    )

    record_activity_event(
        claw_id=claw_id,
        event_type=event_type,
        summary=summary,
        metadata={
            "action": action,
            "previous_status": claw["status"],
            "status": updated["status"],
        },
    )

    return {"id": updated["id"], "status": updated["status"]}


@router.post("/{claw_id}/pause")
async def pause_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _transition_claw(
        claw_id=claw_id,
        user_id=user_id,
        target_status="paused",
        event_type="claw_paused",
        summary="Claw paused",
        action="pause",
    )


@router.post("/{claw_id}/resume")
async def resume_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _transition_claw(
        claw_id=claw_id,
        user_id=user_id,
        target_status="healthy",
        event_type="claw_restarted",
        summary="Claw resumed",
        action="resume",
    )


@router.post("/{claw_id}/restart")
async def restart_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    claw = verify_claw_ownership(claw_id, user_id)
    _ensure_transition(claw["status"], "restarting")

    restarting = _persist_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        current_status=claw["status"],
        target_status="restarting",
    )
    _ensure_transition(restarting["status"], "healthy")

    updated = _persist_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        current_status=restarting["status"],
        target_status="healthy",
    )

    record_activity_event(
        claw_id=claw_id,
        event_type="claw_restarted",
        summary="Claw restarted",
        metadata={
            "action": "restart",
            "previous_status": claw["status"],
            "intermediate_status": restarting["status"],
            "status": updated["status"],
        },
    )

    return {"id": updated["id"], "status": updated["status"]}


@router.post("/{claw_id}/recover")
async def recover_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _transition_claw(
        claw_id=claw_id,
        user_id=user_id,
        target_status="provisioning",
        event_type="claw_recovered",
        summary="Claw recovery started",
        action="recover",
    )
