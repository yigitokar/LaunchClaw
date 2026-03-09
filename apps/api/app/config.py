from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LaunchClaw API"
    app_env: str = "development"
    cors_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_prefix="LAUNCHCLAW_", case_sensitive=False)


settings = Settings()

