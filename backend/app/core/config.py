from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./db.sqlite3"
    openai_api_key: str = ""
    app_name: str = "Voico Calls Dashboard"
    stale_expiry_interval_seconds: int = 600
    stale_expiry_threshold_seconds: int = 1800


settings = Settings()
