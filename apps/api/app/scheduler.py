import logging
from datetime import datetime, timezone
from typing import Any

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from app.db import get_supabase
from app.routers._helpers import record_activity_event


logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_next_run_at(schedule_expr: str, *, base_time: datetime | None = None) -> datetime:
    reference_time = _to_utc(base_time or utc_now())

    try:
        next_run_at = croniter(schedule_expr, reference_time).get_next(datetime)
    except (CroniterBadCronError, CroniterBadDateError, ValueError) as exc:
        raise ValueError("Invalid cron expression") from exc

    return _to_utc(next_run_at)


def create_scheduled_run(*, schedule: dict[str, Any], trigger_source: str) -> dict[str, Any]:
    run_result = (
        get_supabase()
        .table("runs")
        .insert(
            {
                "claw_id": schedule["claw_id"],
                "trigger_type": "scheduled",
                "status": "queued",
                "input_summary": f"Scheduled run: {schedule['name']}",
            }
        )
        .execute()
    )
    run = run_result.data[0]

    record_activity_event(
        claw_id=schedule["claw_id"],
        run_id=run["id"],
        event_type="schedule_triggered",
        summary=f"Schedule triggered: {schedule['name']}",
        metadata={
            "schedule_id": schedule["id"],
            "name": schedule["name"],
            "schedule_expr": schedule["schedule_expr"],
            "last_run_at": schedule.get("last_run_at"),
            "next_run_at": schedule.get("next_run_at"),
            "run_id": run["id"],
            "status": run["status"],
            "trigger_source": trigger_source,
        },
    )

    return run


def tick_scheduler(*, now: datetime | None = None) -> dict[str, Any]:
    scan_time = _to_utc(now or utc_now())
    scan_time_iso = scan_time.isoformat()
    supabase = get_supabase()

    result = (
        supabase.table("schedules")
        .select("id, claw_id, name, schedule_expr, enabled, last_run_at, next_run_at")
        .eq("enabled", True)
        .lte("next_run_at", scan_time_iso)
        .order("next_run_at")
        .execute()
    )

    schedules = result.data or []
    triggered_schedule_ids: list[str] = []
    triggered_count = 0

    for schedule in schedules:
        try:
            next_run_at = compute_next_run_at(schedule["schedule_expr"], base_time=scan_time)
            claimed = (
                supabase.table("schedules")
                .update(
                    {
                        "last_run_at": scan_time_iso,
                        "next_run_at": next_run_at.isoformat(),
                        "updated_at": scan_time_iso,
                    }
                )
                .eq("id", schedule["id"])
                .eq("enabled", True)
                .eq("next_run_at", schedule["next_run_at"])
                .execute()
            )
            if not claimed.data:
                continue

            claimed_schedule = claimed.data[0]
            create_scheduled_run(schedule=claimed_schedule, trigger_source="scheduler")
            triggered_schedule_ids.append(schedule["id"])
            triggered_count += 1
        except Exception:
            logger.exception("Failed to trigger schedule %s", schedule["id"])

    return {
        "scanned_at": scan_time_iso,
        "due_count": len(schedules),
        "triggered_count": triggered_count,
        "triggered_schedule_ids": triggered_schedule_ids,
    }
