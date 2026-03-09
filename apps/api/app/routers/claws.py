from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_supabase
from app.routers._helpers import record_activity_event

router = APIRouter(prefix="/api/claws", tags=["claws"])


class CreateClawRequest(BaseModel):
    name: str = Field(..., min_length=1)
    preset_id: str
    model_access_mode: str = Field(..., pattern="^(byok|managed)$")


class UpdateClawRequest(BaseModel):
    name: str = Field(..., min_length=1)


@router.post("")
async def create_claw(
    body: CreateClawRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    supabase = get_supabase()

    # Validate preset exists
    preset_result = (
        supabase.table("presets")
        .select("id, seed_profile_md, seed_mission_md, seed_rules_md")
        .eq("id", body.preset_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not preset_result.data:
        raise HTTPException(status_code=400, detail={"code": "invalid_preset", "message": "Preset not found"})

    preset = preset_result.data

    # Enforce one active claw per user
    existing = (
        supabase.table("claws")
        .select("id")
        .eq("user_id", user_id)
        .neq("status", "deleted")
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail={"code": "claw_limit", "message": "You already have an active Claw"},
        )

    # Insert the claw
    claw_result = (
        supabase.table("claws")
        .insert(
            {
                "user_id": user_id,
                "name": body.name,
                "preset_id": body.preset_id,
                "model_access_mode": body.model_access_mode,
                "status": "creating",
            }
        )
        .execute()
    )
    claw = claw_result.data[0]

    # Seed workspace files from preset
    seed_files = []
    seed_map = {
        "profile.md": ("profile", preset.get("seed_profile_md")),
        "mission.md": ("mission", preset.get("seed_mission_md")),
        "rules.md": ("rules", preset.get("seed_rules_md")),
    }
    for path, (kind, content) in seed_map.items():
        if content:
            seed_files.append(
                {
                    "claw_id": claw["id"],
                    "path": path,
                    "kind": kind,
                    "content_type": "text/markdown",
                    "storage_ref": f"workspaces/{claw['id']}/{path}",
                    "version": 1,
                    "is_desired_state": True,
                }
            )

    if seed_files:
        supabase.table("workspace_files").insert(seed_files).execute()

    record_activity_event(
        claw_id=claw["id"],
        event_type="claw_created",
        summary="Claw created",
        metadata={
            "status": claw["status"],
            "preset_id": claw["preset_id"],
            "model_access_mode": claw["model_access_mode"],
        },
    )

    return claw


@router.get("")
async def list_claws(user_id: str = Depends(get_current_user_id)) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("claws")
        .select("id, name, status, preset_id, last_active_at, created_at")
        .eq("user_id", user_id)
        .neq("status", "deleted")
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": result.data, "next_cursor": None}


@router.get("/{claw_id}")
async def get_claw(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("claws")
        .select("*")
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Claw not found"})
    return result.data


@router.patch("/{claw_id}")
async def update_claw(
    claw_id: str,
    body: UpdateClawRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    supabase = get_supabase()

    # Verify ownership
    existing = (
        supabase.table("claws")
        .select("id")
        .eq("id", claw_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Claw not found"})

    result = (
        supabase.table("claws")
        .update({"name": body.name})
        .eq("id", claw_id)
        .execute()
    )
    return result.data[0]
