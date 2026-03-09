from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership
from app.services.lifecycle import validate_transition


router = APIRouter(prefix="/api/claws", tags=["lifecycle"])


def _update_claw_status(
    *,
    claw_id: str,
    user_id: str,
    target_status: str,
    event_type: str,
    summary: str,
    action: str,
) -> dict[str, Any]:
    current_claw = verify_claw_ownership(claw_id, user_id)

    try:
        persisted_target = validate_transition(current_claw["status"], target_status)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc

    updated_at = datetime.now(timezone.utc).isoformat()
    result = (
        get_supabase()
        .table("claws")
        .update({"status": persisted_target, "updated_at": updated_at})
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .eq("status", current_claw["status"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_transition",
                "message": "Claw status changed before this action completed. Refresh and try again.",
            },
        )

    updated_claw = result.data[0]
    record_activity_event(
        claw_id=claw_id,
        event_type=event_type,
        summary=summary,
        metadata={
            "action": action,
            "previous_status": current_claw["status"],
            "status": updated_claw["status"],
        },
    )

    return {"id": updated_claw["id"], "status": updated_claw["status"]}


@router.post("/{claw_id}/pause")
async def pause_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _update_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        target_status="paused",
        event_type="claw_paused",
        summary="Claw paused",
        action="pause",
    )


@router.post("/{claw_id}/resume")
async def resume_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _update_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        target_status="provisioning",
        event_type="claw_resumed",
        summary="Claw resumed",
        action="resume",
    )


@router.post("/{claw_id}/restart")
async def restart_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _update_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        target_status="restarting",
        event_type="claw_restarted",
        summary="Claw restart requested",
        action="restart",
    )


@router.post("/{claw_id}/recover")
async def recover_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _update_claw_status(
        claw_id=claw_id,
        user_id=user_id,
        target_status="provisioning",
        event_type="claw_recovered",
        summary="Claw recovery started",
        action="recover",
    )

