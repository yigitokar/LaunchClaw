from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.middleware.error_handler import ErrorHandlerMiddleware, register_error_handlers
from app.routers.activity import router as activity_router
from app.routers.approvals import router as approvals_router
from app.routers.billing import router as billing_router
from app.routers.claws import router as claws_router
from app.routers.integrations import router as integrations_router
from app.routers.internal import router as internal_router
from app.routers.lifecycle import router as lifecycle_router
from app.routers.runs import router as runs_router
from app.routers.schedules import router as schedules_router
from app.routers.secrets import router as secrets_router
from app.routers.workspace_files import router as workspace_files_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Control-plane API scaffold derived from the LaunchClaw v1 docs.",
)

register_error_handlers(app)
app.add_middleware(ErrorHandlerMiddleware)
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
app.include_router(integrations_router)
app.include_router(approvals_router)
app.include_router(secrets_router)
app.include_router(internal_router)
app.include_router(billing_router)


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
