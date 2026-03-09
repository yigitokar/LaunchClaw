from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.routers.claws import router as claws_router


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
