from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import verify_claw_ownership

router = APIRouter(prefix="/api/claws/{claw_id}/workspace/files", tags=["workspace-files"])


@router.get("")
async def list_files(
    claw_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    verify_claw_ownership(claw_id, user_id)
    supabase = get_supabase()
    result = (
        supabase.table("workspace_files")
        .select("id, path, kind, is_desired_state, version, updated_at")
        .eq("claw_id", claw_id)
        .order("path")
        .execute()
    )
    return {"items": result.data}


@router.get("/content")
async def get_file_content(
    claw_id: str,
    path: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    verify_claw_ownership(claw_id, user_id)
    supabase = get_supabase()
    result = (
        supabase.table("workspace_files")
        .select("path, kind, content_type, storage_ref, version, updated_at")
        .eq("claw_id", claw_id)
        .eq("path", path)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "File not found"})

    file = result.data
    return {
        "path": file["path"],
        "kind": file["kind"],
        "content": file.get("storage_ref", ""),
        "version": file["version"],
        "updated_at": file["updated_at"],
    }


class UpdateFileRequest(BaseModel):
    path: str = Field(..., min_length=1)
    content: str
    base_version: int = Field(..., ge=1)


@router.put("/content")
async def update_file_content(
    claw_id: str,
    body: UpdateFileRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    verify_claw_ownership(claw_id, user_id)
    supabase = get_supabase()

    # Fetch current file to check version
    existing = (
        supabase.table("workspace_files")
        .select("id, version, is_desired_state")
        .eq("claw_id", claw_id)
        .eq("path", body.path)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "File not found"})

    file = existing.data
    if not file["is_desired_state"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Only desired-state files can be edited"},
        )

    if file["version"] != body.base_version:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "message": "File has been modified since you last read it"},
        )

    new_version = file["version"] + 1
    result = (
        supabase.table("workspace_files")
        .update({"storage_ref": body.content, "version": new_version})
        .eq("id", file["id"])
        .eq("version", body.base_version)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "message": "File has been modified since you last read it"},
        )

    updated = result.data[0]
    return {
        "path": body.path,
        "version": updated["version"],
        "updated_at": updated["updated_at"],
    }
