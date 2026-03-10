from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import verify_internal_service
from app.db import get_supabase
from app.routers._helpers import record_activity_event
from app.services.github_app import mint_github_installation_token, require_github_app_credentials
from app.services.scheduler import process_due_schedules

router = APIRouter(tags=["internal"])


class MintGitHubTokenRequest(BaseModel):
    claw_id: str
    integration_id: str
    repositories: list[str] = Field(default_factory=list)
    permissions: dict[str, str] = Field(default_factory=dict)


class CreateApprovalRequest(BaseModel):
    claw_id: str
    run_id: str | None = None
    action_type: str = Field(..., min_length=1, max_length=80)
    payload_summary: str | None = Field(default=None, max_length=500)


@router.post("/internal/scheduler/tick")
async def scheduler_tick(_: None = Depends(verify_internal_service)) -> dict[str, Any]:
    return process_due_schedules()


@router.post("/internal/approvals")
async def create_approval(
    body: CreateApprovalRequest,
    _: None = Depends(verify_internal_service),
) -> dict[str, str]:
    supabase = get_supabase()
    claw_result = (
        supabase.table("claws")
        .select("id")
        .eq("id", body.claw_id)
        .maybe_single()
        .execute()
    )
    if not claw_result.data:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Claw not found"},
        )

    if body.run_id:
        existing_pending = (
            supabase.table("approvals")
            .select("id, status")
            .eq("claw_id", body.claw_id)
            .eq("run_id", body.run_id)
            .eq("action_type", body.action_type)
            .eq("status", "pending")
            .maybe_single()
            .execute()
        )
        if existing_pending.data:
            return {"id": existing_pending.data["id"], "status": existing_pending.data["status"]}

        run_result = (
            supabase.table("runs")
            .select("id, claw_id, status")
            .eq("id", body.run_id)
            .eq("claw_id", body.claw_id)
            .maybe_single()
            .execute()
        )
        run = run_result.data
        if not run:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Run not found"},
            )
        if run["status"] in {"succeeded", "failed", "cancelled"}:
            raise HTTPException(
                status_code=409,
                detail={"code": "conflict", "message": "Run cannot request approval from its current status"},
            )

        (
            supabase.table("runs")
            .update({"status": "waiting_approval", "approval_state": "pending"})
            .eq("id", body.run_id)
            .eq("claw_id", body.claw_id)
            .execute()
        )

    approval_id = f"approval_{secrets.token_hex(6)}"
    result = (
        supabase.table("approvals")
        .insert(
            {
                "id": approval_id,
                "claw_id": body.claw_id,
                "run_id": body.run_id,
                "action_type": body.action_type,
                "payload_summary": body.payload_summary,
                "status": "pending",
            }
        )
        .execute()
    )
    approval = result.data[0]

    record_activity_event(
        claw_id=body.claw_id,
        run_id=body.run_id,
        event_type="approval_requested",
        summary="Approval requested",
        metadata={
            "approval_id": approval["id"],
            "action_type": approval["action_type"],
            "status": approval["status"],
            "payload_summary": approval.get("payload_summary"),
        },
    )

    return {"id": approval["id"], "status": approval["status"]}


@router.get("/internal/approvals/{approval_id}")
async def get_internal_approval(
    approval_id: str,
    _: None = Depends(verify_internal_service),
) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("approvals")
        .select("id, status, resolved_at")
        .eq("id", approval_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Approval not found"},
        )
    return result.data


@router.post("/internal/integrations/github/token")
async def mint_github_token(
    body: MintGitHubTokenRequest,
    _: None = Depends(verify_internal_service),
) -> dict[str, str]:
    require_github_app_credentials()

    result = (
        get_supabase()
        .table("integrations")
        .select("id, claw_id, provider, status, external_account_ref")
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

    installation_id = integration.get("external_account_ref")
    if not installation_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "GitHub integration is missing its installation reference"},
        )

    return mint_github_installation_token(
        str(installation_id),
        body.repositories,
        body.permissions,
    )
