from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership
from app.services.scheduler import compute_next_run_at, utc_now, validate_schedule_expr

router = APIRouter(prefix="/api/claws/{claw_id}/schedules", tags=["schedules"])

SCHEDULE_RESPONSE_FIELDS = "id, claw_id, name, schedule_expr, enabled, last_run_at, next_run_at, created_at, updated_at"


class SchedulePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    schedule_expr: str = Field(..., min_length=1)
    enabled: bool = True


class ToggleScheduleRequest(BaseModel):
    enabled: bool


def normalize_schedule_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Schedule name is required"},
        )
    return normalized


def get_schedule_for_claw(claw_id: str, schedule_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("schedules")
        .select(SCHEDULE_RESPONSE_FIELDS)
        .eq("id", schedule_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found"})
    return result.data


@router.get("")
async def list_schedules(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, list[dict[str, Any]]]:
    verify_claw_ownership(claw_id, user_id)

    result = (
        get_supabase()
        .table("schedules")
        .select(SCHEDULE_RESPONSE_FIELDS)
        .eq("claw_id", claw_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": result.data or []}


@router.post("")
async def create_schedule(
    claw_id: str,
    body: SchedulePayload,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    name = normalize_schedule_name(body.name)
    schedule_expr = validate_schedule_expr(body.schedule_expr)
    next_run_at = compute_next_run_at(schedule_expr) if body.enabled else None

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
            }
        )
        .execute()
    )
    schedule = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="schedule_created",
        summary=f"Schedule created: {name}",
        metadata={
            "schedule_id": schedule["id"],
            "schedule_name": name,
            "schedule_expr": schedule_expr,
            "enabled": body.enabled,
        },
    )

    return schedule


@router.put("/{schedule_id}")
async def update_schedule(
    claw_id: str,
    schedule_id: str,
    body: SchedulePayload,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    existing = get_schedule_for_claw(claw_id, schedule_id)

    name = normalize_schedule_name(body.name)
    schedule_expr = validate_schedule_expr(body.schedule_expr)
    next_run_at = compute_next_run_at(schedule_expr) if body.enabled else None

    result = (
        get_supabase()
        .table("schedules")
        .update(
            {
                "name": name,
                "schedule_expr": schedule_expr,
                "enabled": body.enabled,
                "next_run_at": next_run_at,
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
        summary=f"Schedule updated: {name}",
        metadata={
            "schedule_id": schedule_id,
            "previous_name": existing["name"],
            "schedule_name": name,
            "schedule_expr": schedule_expr,
            "enabled": body.enabled,
        },
    )

    return schedule


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(
    claw_id: str,
    schedule_id: str,
    body: ToggleScheduleRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)
    existing = get_schedule_for_claw(claw_id, schedule_id)

    next_run_at = compute_next_run_at(existing["schedule_expr"], base_time=utc_now()) if body.enabled else None
    result = (
        get_supabase()
        .table("schedules")
        .update({"enabled": body.enabled, "next_run_at": next_run_at})
        .eq("id", schedule_id)
        .eq("claw_id", claw_id)
        .execute()
    )
    schedule = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="schedule_toggled",
        summary=f"Schedule {'enabled' if body.enabled else 'disabled'}: {existing['name']}",
        metadata={
            "schedule_id": schedule_id,
            "schedule_name": existing["name"],
            "enabled": body.enabled,
        },
    )

    return schedule
