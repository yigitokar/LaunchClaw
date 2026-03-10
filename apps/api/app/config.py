from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LaunchClaw API"
    app_env: str = "development"
    cors_origin: str = "http://localhost:3000"
    frontend_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL", "LAUNCHCLAW_FRONTEND_URL"),
    )
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_key: str = ""
    internal_service_token: str = ""
    secret_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices("SECRET_ENCRYPTION_KEY", "LAUNCHCLAW_SECRET_ENCRYPTION_KEY"),
    )
    stripe_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "LAUNCHCLAW_STRIPE_SECRET_KEY"),
    )
    stripe_price_id_starter: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_STARTER", "LAUNCHCLAW_STRIPE_PRICE_ID_STARTER"),
    )
    github_app_slug: str = "launchclaw"
    github_app_state_secret: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    model_config = SettingsConfigDict(env_prefix="LAUNCHCLAW_", case_sensitive=False)


settings = Settings()
