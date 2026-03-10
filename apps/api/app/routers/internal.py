import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import verify_internal_service
from app.db import get_supabase
from app.services.scheduler import process_due_schedules
from app.services.scheduler import utc_now

router = APIRouter(tags=["internal"])


class MintGitHubTokenRequest(BaseModel):
    claw_id: str
    integration_id: str
    repositories: list[str] = Field(default_factory=list)
    permissions: dict[str, str] = Field(default_factory=dict)


@router.post("/internal/scheduler/tick")
async def scheduler_tick(_: None = Depends(verify_internal_service)) -> dict[str, Any]:
    return process_due_schedules()


@router.post("/internal/integrations/github/token")
async def mint_github_token(
    body: MintGitHubTokenRequest,
    _: None = Depends(verify_internal_service),
) -> dict[str, str]:
    result = (
        get_supabase()
        .table("integrations")
        .select("id, claw_id, provider, status")
        .eq("id", body.integration_id)
        .eq("claw_id", body.claw_id)
        .eq("provider", "github")
        .maybe_single()
        .execute()
    )
    integration = result.data
    if not integration:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "GitHub integration not found"},
        )
    if integration["status"] != "connected":
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "GitHub integration is not connected"},
        )

    expires_at = (utc_now() + timedelta(hours=1)).isoformat()
    return {"token": f"ghs_{secrets.token_urlsafe(24)}", "expires_at": expires_at}
