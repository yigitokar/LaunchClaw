from typing import Any

from fastapi import HTTPException

from app.db import get_supabase


def verify_claw_ownership(claw_id: str, user_id: str) -> dict[str, Any]:
    """Raise 404 if the claw does not exist or is not owned by the user."""
    supabase = get_supabase()
    result = (
        supabase.table("claws")
        .select("id, name, status")
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Claw not found"})
    return result.data


def get_run_for_user(run_id: str, user_id: str) -> dict[str, Any]:
    """Return a run after verifying its parent claw belongs to the user."""
    supabase = get_supabase()
    result = supabase.table("runs").select("*").eq("id", run_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Run not found"})

    run = result.data
    verify_claw_ownership(run["claw_id"], user_id)
    return run


def parse_offset_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0

    try:
        offset = int(cursor)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Invalid cursor"},
        ) from exc

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Invalid cursor"},
        )

    return offset


def build_next_cursor(offset: int, limit: int, result_count: int) -> str | None:
    if result_count <= limit:
        return None
    return str(offset + limit)


def record_activity_event(
    *,
    claw_id: str,
    event_type: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "claw_id": claw_id,
        "type": event_type,
        "summary": summary,
        "metadata": metadata or {},
    }
    if run_id is not None:
        payload["run_id"] = run_id

    get_supabase().table("activity_events").insert(payload).execute()
