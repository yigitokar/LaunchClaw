import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from app.db import get_supabase
from app.routers._helpers import record_activity_event


logger = logging.getLogger(__name__)
SCHEDULER_POLL_INTERVAL_SECONDS = 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_next_run_at(schedule_expr: str, *, base_time: datetime | None = None) -> datetime:
    reference_time = base_time or utc_now()
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    try:
        next_run = croniter(schedule_expr, reference_time).get_next(datetime)
    except (CroniterBadCronError, CroniterBadDateError, ValueError) as exc:
        raise ValueError("Invalid cron expression") from exc

    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=timezone.utc)

    return next_run.astimezone(timezone.utc)


def scan_due_schedules(*, now: datetime | None = None) -> dict[str, Any]:
    scan_time = now or utc_now()
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
    triggered_count = 0
    triggered_schedule_ids: list[str] = []

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

            run_result = (
                supabase.table("runs")
                .insert(
                    {
                        "claw_id": schedule["claw_id"],
                        "trigger_type": "schedule",
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
                    "schedule_name": schedule["name"],
                    "schedule_expr": schedule["schedule_expr"],
                    "run_id": run["id"],
                    "status": run["status"],
                    "next_run_at": next_run_at.isoformat(),
                },
            )

            triggered_count += 1
            triggered_schedule_ids.append(schedule["id"])
        except Exception:
            logger.exception("Failed to trigger schedule %s", schedule["id"])

    return {
        "scanned_at": scan_time_iso,
        "due_count": len(schedules),
        "triggered_count": triggered_count,
        "triggered_schedule_ids": triggered_schedule_ids,
    }


async def run_scheduler_loop(*, poll_interval_seconds: int = SCHEDULER_POLL_INTERVAL_SECONDS) -> None:
    while True:
        try:
            await asyncio.to_thread(scan_due_schedules)
        except Exception:
            logger.exception("Failed to scan due schedules")

        await asyncio.sleep(poll_interval_seconds)
