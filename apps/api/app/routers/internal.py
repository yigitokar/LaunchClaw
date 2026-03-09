from typing import Any

from fastapi import APIRouter, Depends

from app.auth import verify_internal_service
from app.services.scheduler import process_due_schedules

router = APIRouter(tags=["internal"])


@router.post("/internal/scheduler/tick")
async def scheduler_tick(_: None = Depends(verify_internal_service)) -> dict[str, Any]:
    return process_due_schedules()
