from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LaunchClaw API"
    app_env: str = "development"
    cors_origin: str = "http://localhost:3000"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_key: str = ""

    model_config = SettingsConfigDict(env_prefix="LAUNCHCLAW_", case_sensitive=False)


settings = Settings()

