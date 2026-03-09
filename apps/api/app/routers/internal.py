import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.scheduler import tick_scheduler


router = APIRouter(tags=["internal"])


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _require_internal_service_token(x_internal_token: str | None) -> None:
    expected = settings.internal_service_token
    if not expected or not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail=_detail("unauthorized", "Invalid internal token"))


@router.post("/internal/scheduler/tick")
async def scheduler_tick(
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
) -> dict[str, Any]:
    _require_internal_service_token(x_internal_token)
    return tick_scheduler()
