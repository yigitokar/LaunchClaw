from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import (
    build_next_cursor,
    get_run_for_user,
    parse_offset_cursor,
    record_activity_event,
    verify_claw_ownership,
)

router = APIRouter(tags=["runs"])


class CreateRunRequest(BaseModel):
    input: str = Field(..., min_length=1)


def _summarize_input(raw_input: str) -> str:
    summary = raw_input.strip()
    if not summary:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "Input cannot be empty"},
        )
    if len(summary) > 500:
        return f"{summary[:497]}..."
    return summary


@router.post("/api/claws/{claw_id}/runs")
async def create_run(
    claw_id: str,
    body: CreateRunRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    summary = _summarize_input(body.input)
    result = (
        get_supabase()
        .table("runs")
        .insert(
            {
                "claw_id": claw_id,
                "trigger_type": "manual",
                "status": "queued",
                "input_summary": summary,
            }
        )
        .execute()
    )
    run = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        run_id=run["id"],
        event_type="run_started",
        summary="Manual run started",
        metadata={
            "run_id": run["id"],
            "trigger_type": run["trigger_type"],
            "status": run["status"],
            "input_summary": summary,
        },
    )

    return {
        "id": run["id"],
        "claw_id": run["claw_id"],
        "trigger_type": run["trigger_type"],
        "status": run["status"],
        "created_at": run["created_at"],
    }


@router.get("/api/claws/{claw_id}/runs")
async def list_runs(
    claw_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    offset = parse_offset_cursor(cursor)
    result = (
        get_supabase()
        .table("runs")
        .select(
            "id, claw_id, trigger_type, status, input_summary, approval_state, created_at, started_at, ended_at"
        )
        .eq("claw_id", claw_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit)
        .execute()
    )

    items = result.data or []
    return {
        "items": items[:limit],
        "next_cursor": build_next_cursor(offset, limit, len(items)),
    }


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return get_run_for_user(run_id, user_id)
