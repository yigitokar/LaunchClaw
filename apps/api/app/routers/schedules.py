from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership
from app.services.scheduler import compute_next_run_at


router = APIRouter(tags=["schedules"])


class SchedulePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    schedule_expr: str = Field(..., min_length=1, max_length=120)
    enabled: bool = True


class ToggleSchedulePayload(BaseModel):
    enabled: bool


def _clean_schedule_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Schedule name cannot be empty"},
        )
    return cleaned


def _clean_schedule_expr(schedule_expr: str) -> str:
    cleaned = schedule_expr.strip()
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Cron expression cannot be empty"},
        )
    return cleaned


def _validated_next_run_at(schedule_expr: str, *, enabled: bool) -> str | None:
    if not enabled:
        return None

    try:
        return compute_next_run_at(schedule_expr).isoformat()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": str(exc)},
        ) from exc


def _get_schedule_for_claw(claw_id: str, schedule_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("schedules")
        .select("*")
        .eq("id", schedule_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found"})
    return result.data


def _schedule_event_metadata(schedule: dict[str, Any]) -> dict[str, Any]:
    return {
        "schedule_id": schedule["id"],
        "name": schedule["name"],
        "schedule_expr": schedule["schedule_expr"],
        "enabled": schedule["enabled"],
        "last_run_at": schedule.get("last_run_at"),
        "next_run_at": schedule.get("next_run_at"),
    }


@router.get("/api/claws/{claw_id}/schedules")
async def list_schedules(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    result = (
        get_supabase()
        .table("schedules")
        .select("id, claw_id, name, schedule_expr, enabled, last_run_at, next_run_at, created_at, updated_at")
        .eq("claw_id", claw_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": result.data or []}


@router.post("/api/claws/{claw_id}/schedules")
async def create_schedule(
    claw_id: str,
    body: SchedulePayload,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    name = _clean_schedule_name(body.name)
    schedule_expr = _clean_schedule_expr(body.schedule_expr)
    now = datetime.now(timezone.utc).isoformat()
    next_run_at = _validated_next_run_at(schedule_expr, enabled=body.enabled)

    result = (
        get_supabase()
        .table("schedules")
        .insert(
            {
                "claw_id": claw_id,
                "name": name,
                "schedule_expr": schedule_expr,
                "enabled": body.enabled,
                "next_run_at": next_run_at,
                "updated_at": now,
            }
        )
        .execute()
    )
    schedule = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="schedule_created",
        summary=f"Schedule created: {schedule['name']}",
        metadata=_schedule_event_metadata(schedule),
    )

    return schedule


@router.put("/api/claws/{claw_id}/schedules/{schedule_id}")
async def update_schedule(
    claw_id: str,
    schedule_id: str,
    body: SchedulePayload,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    existing = _get_schedule_for_claw(claw_id, schedule_id)

    name = _clean_schedule_name(body.name)
    schedule_expr = _clean_schedule_expr(body.schedule_expr)
    now = datetime.now(timezone.utc).isoformat()
    next_run_at = _validated_next_run_at(schedule_expr, enabled=body.enabled)

    result = (
        get_supabase()
        .table("schedules")
        .update(
            {
                "name": name,
                "schedule_expr": schedule_expr,
                "enabled": body.enabled,
                "next_run_at": next_run_at,
                "updated_at": now,
            }
        )
        .eq("id", schedule_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    schedule = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="schedule_updated",
        summary=f"Schedule updated: {schedule['name']}",
        metadata={
            "previous_name": existing["name"],
            "previous_schedule_expr": existing["schedule_expr"],
            "previous_enabled": existing["enabled"],
            **_schedule_event_metadata(schedule),
        },
    )

    return schedule


@router.post("/api/claws/{claw_id}/schedules/{schedule_id}/toggle")
async def toggle_schedule(
    claw_id: str,
    schedule_id: str,
    body: ToggleSchedulePayload,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    existing = _get_schedule_for_claw(claw_id, schedule_id)
    now = datetime.now(timezone.utc).isoformat()
    next_run_at = _validated_next_run_at(existing["schedule_expr"], enabled=body.enabled)

    result = (
        get_supabase()
        .table("schedules")
        .update(
            {
                "enabled": body.enabled,
                "next_run_at": next_run_at,
                "updated_at": now,
            }
        )
        .eq("id", schedule_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    schedule = result.data[0]
    event_type = "schedule_enabled" if body.enabled else "schedule_disabled"
    summary = f"Schedule {'enabled' if body.enabled else 'disabled'}: {schedule['name']}"

    record_activity_event(
        claw_id=claw_id,
        event_type=event_type,
        summary=summary,
        metadata=_schedule_event_metadata(schedule),
    )

    return schedule


@router.delete("/api/claws/{claw_id}/schedules/{schedule_id}")
async def delete_schedule(
    claw_id: str,
    schedule_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    existing = _get_schedule_for_claw(claw_id, schedule_id)

    get_supabase().table("schedules").delete().eq("id", schedule_id).eq("claw_id", claw_id).execute()

    record_activity_event(
        claw_id=claw_id,
        event_type="schedule_deleted",
        summary=f"Schedule deleted: {existing['name']}",
        metadata=_schedule_event_metadata(existing),
    )

    return {"id": schedule_id, "deleted": True}

