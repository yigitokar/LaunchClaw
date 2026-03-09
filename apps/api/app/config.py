from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LaunchClaw API"
    app_env: str = "development"
    cors_origin: str = "http://localhost:3000"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_key: str = ""
    internal_service_token: str = ""
    github_app_slug: str = "launchclaw"
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    model_config = SettingsConfigDict(env_prefix="LAUNCHCLAW_", case_sensitive=False)


settings = Settings()
