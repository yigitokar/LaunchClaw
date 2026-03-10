from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import (
    build_next_cursor,
    parse_offset_cursor,
    record_activity_event,
    verify_claw_ownership,
)
from app.services.scheduler import utc_now

router = APIRouter(tags=["approvals"])

APPROVAL_RESPONSE_FIELDS = (
    "id, claw_id, run_id, action_type, payload_summary, status, requested_at, resolved_at, created_at"
)


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _get_approval_for_user(approval_id: str, user_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("approvals")
        .select(APPROVAL_RESPONSE_FIELDS)
        .eq("id", approval_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Approval not found"))

    approval = result.data
    verify_claw_ownership(approval["claw_id"], user_id)
    return approval


def _resolve_approval(approval_id: str, user_id: str, next_status: str) -> dict[str, Any]:
    approval = _get_approval_for_user(approval_id, user_id)
    if approval["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=_detail("invalid_state", "Approval has already been resolved"),
        )

    resolved_at = utc_now().isoformat()
    result = (
        get_supabase()
        .table("approvals")
        .update({"status": next_status, "resolved_at": resolved_at})
        .eq("id", approval_id)
        .eq("status", "pending")
        .execute()
    )
    items = result.data or []
    if not items:
        raise HTTPException(
            status_code=409,
            detail=_detail("invalid_state", "Approval has already been resolved"),
        )

    updated = items[0]
    run_id = updated.get("run_id")
    if run_id is not None:
        run_update: dict[str, Any] = {"approval_state": next_status}
        if next_status == "approved":
            run_update["status"] = "queued"
        else:
            run_update["status"] = "cancelled"
            run_update["ended_at"] = resolved_at

        (
            get_supabase()
            .table("runs")
            .update(run_update)
            .eq("id", run_id)
            .eq("approval_state", "pending")
            .execute()
        )

    record_activity_event(
        claw_id=updated["claw_id"],
        run_id=run_id,
        event_type=f"approval_{next_status}",
        summary=f"Approval {next_status}",
        metadata={
            "approval_id": updated["id"],
            "action_type": updated["action_type"],
            "status": updated["status"],
            "payload_summary": updated.get("payload_summary"),
        },
    )

    return updated


@router.get("/api/claws/{claw_id}/approvals")
async def list_approvals(
    claw_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    status: str | None = Query(None, pattern="^(pending|approved|denied)$"),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    offset = parse_offset_cursor(cursor)
    query = (
        get_supabase()
        .table("approvals")
        .select(APPROVAL_RESPONSE_FIELDS)
        .eq("claw_id", claw_id)
        .order("requested_at", desc=True)
        .order("id", desc=True)
    )
    if status:
        query = query.eq("status", status)

    result = query.range(offset, offset + limit).execute()
    items = result.data or []
    return {
        "items": items[:limit],
        "next_cursor": build_next_cursor(offset, limit, len(items)),
    }


@router.get("/api/approvals/{approval_id}")
async def get_approval(approval_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _get_approval_for_user(approval_id, user_id)


@router.post("/api/approvals/{approval_id}/approve")
async def approve_approval(approval_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _resolve_approval(approval_id, user_id, "approved")


@router.post("/api/approvals/{approval_id}/deny")
async def deny_approval(approval_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _resolve_approval(approval_id, user_id, "denied")
