from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership

router = APIRouter(prefix="/api/claws", tags=["lifecycle"])

TRANSITIONS: dict[str, dict[str, Any]] = {
    "pause": {
        "allowed_statuses": {"healthy", "degraded"},
        "next_status": "paused",
        "event_type": "claw_paused",
        "summary": "Claw paused",
    },
    "resume": {
        "allowed_statuses": {"paused"},
        "next_status": "provisioning",
        "event_type": "claw_resumed",
        "summary": "Claw resumed",
    },
    "restart": {
        "allowed_statuses": {"healthy", "degraded"},
        "next_status": "restarting",
        "event_type": "claw_restarted",
        "summary": "Claw restarted",
    },
    "recover": {
        "allowed_statuses": {"failed"},
        "next_status": "provisioning",
        "event_type": "claw_recovered",
        "summary": "Claw recovery started",
    },
}


def apply_lifecycle_transition(claw_id: str, user_id: str, action: str) -> dict[str, str]:
    claw = verify_claw_ownership(claw_id, user_id)
    transition = TRANSITIONS[action]
    current_status = claw["status"]

    if current_status not in transition["allowed_statuses"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_transition",
                "message": f"Cannot {action} claw from status '{current_status}'",
            },
        )

    next_status = transition["next_status"]
    (
        get_supabase()
        .table("claws")
        .update({"status": next_status})
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .execute()
    )

    record_activity_event(
        claw_id=claw_id,
        event_type=transition["event_type"],
        summary=transition["summary"],
        metadata={"from_status": current_status, "status": next_status},
    )

    return {"id": claw_id, "status": next_status}


@router.post("/{claw_id}/pause")
async def pause_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
    return apply_lifecycle_transition(claw_id, user_id, "pause")


@router.post("/{claw_id}/resume")
async def resume_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
    return apply_lifecycle_transition(claw_id, user_id, "resume")


@router.post("/{claw_id}/restart")
async def restart_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
    return apply_lifecycle_transition(claw_id, user_id, "restart")


@router.post("/{claw_id}/recover")
async def recover_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
    return apply_lifecycle_transition(claw_id, user_id, "recover")
