from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import build_next_cursor, parse_offset_cursor, verify_claw_ownership

router = APIRouter(prefix="/api/claws/{claw_id}/activity", tags=["activity"])


@router.get("")
async def list_activity(
    claw_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    verify_claw_ownership(claw_id, user_id)

    offset = parse_offset_cursor(cursor)
    result = (
        get_supabase()
        .table("activity_events")
        .select("id, type, summary, metadata, created_at")
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
