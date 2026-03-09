from datetime import datetime, timezone
from typing import Any

from croniter import croniter
from fastapi import HTTPException

from app.db import get_supabase
from app.routers._helpers import record_activity_event


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_schedule_expr(schedule_expr: str) -> str:
    normalized = schedule_expr.strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Schedule expression is required"},
        )

    if not croniter.is_valid(normalized):
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Invalid schedule expression"},
        )

    return normalized


def compute_next_run_at(schedule_expr: str, *, base_time: datetime | None = None) -> str:
    base = (base_time or utc_now()).astimezone(timezone.utc)
    next_run = croniter(schedule_expr, base).get_next(datetime)
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=timezone.utc)
    else:
        next_run = next_run.astimezone(timezone.utc)
    return next_run.isoformat()


def build_scheduled_run_summary(name: str) -> str:
    return f"Scheduled run: {name}"


def process_due_schedules() -> dict[str, Any]:
    now = utc_now()
    now_iso = now.isoformat()
    supabase = get_supabase()

    result = (
        supabase.table("schedules")
        .select("id, claw_id, name, schedule_expr, enabled, last_run_at, next_run_at")
        .eq("enabled", True)
        .order("next_run_at")
        .execute()
    )

    due_schedules = [
        schedule
        for schedule in (result.data or [])
        if schedule.get("next_run_at") and parse_timestamp(schedule["next_run_at"]) <= now
    ]

    runs_created: list[dict[str, str]] = []
    for schedule in due_schedules:
        next_run_at = compute_next_run_at(schedule["schedule_expr"], base_time=now)
        run_result = (
            supabase.table("runs")
            .insert(
                {
                    "claw_id": schedule["claw_id"],
                    "trigger_type": "schedule",
                    "status": "queued",
                    "input_summary": build_scheduled_run_summary(schedule["name"]),
                }
            )
            .execute()
        )
        run = run_result.data[0]

        (
            supabase.table("schedules")
            .update({"last_run_at": now_iso, "next_run_at": next_run_at})
            .eq("id", schedule["id"])
            .execute()
        )

        record_activity_event(
            claw_id=schedule["claw_id"],
            run_id=run["id"],
            event_type="schedule_triggered",
            summary=f"Schedule triggered: {schedule['name']}",
            metadata={
                "schedule_id": schedule["id"],
                "schedule_name": schedule["name"],
                "schedule_expr": schedule["schedule_expr"],
                "run_id": run["id"],
            },
        )

        runs_created.append({"schedule_id": schedule["id"], "run_id": run["id"]})

    return {"processed": len(runs_created), "runs_created": runs_created}
