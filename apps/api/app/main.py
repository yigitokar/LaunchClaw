from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


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


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me")
async def get_current_user() -> dict[str, object]:
    return {
        "id": "user_demo",
        "email": "demo@launchclaw.dev",
        "name": "Demo User",
        "billing": {
            "plan": "starter",
            "status": "draft",
        },
    }


@app.get("/api/presets")
async def list_presets() -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {
                "id": "preset_dev_assistant",
                "slug": "dev-assistant",
                "name": "Dev Assistant",
                "description": "Good default for code and GitHub work",
            }
        ]
    }

