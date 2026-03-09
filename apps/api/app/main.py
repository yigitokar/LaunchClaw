import asyncio
from contextlib import suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.routers.activity import router as activity_router
from app.routers.claws import router as claws_router
from app.routers.lifecycle import router as lifecycle_router
from app.routers.runs import router as runs_router
from app.routers.schedules import router as schedules_router
from app.routers.workspace_files import router as workspace_files_router
from app.services.scheduler import run_scheduler_loop


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Control-plane API scaffold derived from the LaunchClaw v1 docs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claws_router)
app.include_router(lifecycle_router)
app.include_router(runs_router)
app.include_router(schedules_router)
app.include_router(activity_router)
app.include_router(workspace_files_router)


@app.on_event("startup")
async def start_scheduler() -> None:
    app.state.scheduler_task = asyncio.create_task(run_scheduler_loop())


@app.on_event("shutdown")
async def stop_scheduler() -> None:
    scheduler_task = getattr(app.state, "scheduler_task", None)
    if scheduler_task is None:
        return

    scheduler_task.cancel()
    with suppress(asyncio.CancelledError):
        await scheduler_task


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me")
async def get_current_user(user_id: str = Depends(get_current_user_id)) -> dict[str, object]:
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    user = result.data

    billing_result = (
        supabase.table("billing_accounts")
        .select("plan, status")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    billing = billing_result.data or {"plan": "none", "status": "inactive"}

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "billing": {
            "plan": billing.get("plan", "none"),
            "status": billing.get("status", "inactive"),
        },
    }


@app.get("/api/presets")
async def list_presets() -> dict[str, object]:
    supabase = get_supabase()
    result = (
        supabase.table("presets")
        .select("id, slug, name, description")
        .eq("is_active", True)
        .execute()
    )
    return {"items": result.data}
