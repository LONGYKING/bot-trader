import json
import os
from functools import lru_cache
from typing import Literal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://bottrader:bottrader@localhost:5432/bottrader"

    # Redis
    redis_dsn: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-to-a-64-char-hex-string"

    # App
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Sentry
    sentry_dsn: str | None = None

    # Google Sheets — accepts either a file path OR inline JSON string
    google_service_account_json: str | None = None
    google_drive_folder_id: str | None = None

    # Cloudinary — fallback export when Google Drive quota is exceeded
    # Set CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name  OR individual vars below
    cloudinary_url: str | None = None
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    # Local backtest export directory (always written regardless of cloud export)
    backtest_export_dir: str = "backtest_exports"

    # Notifications
    # When True, subscribers receive a "market scan" message even when no signal fires
    send_neutral_signals: bool = False

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_long(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def fix_database_url(self) -> "Settings":
        # Auto-upgrade plain postgresql:// → postgresql+asyncpg:// for async SQLAlchemy
        url = self.database_url
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        return self

    @model_validator(mode="after")
    def resolve_google_service_account(self) -> "Settings":
        """If GOOGLE_SERVICE_ACCOUNT_JSON is a file path, read the file contents."""
        val = self.google_service_account_json
        if val and not val.strip().startswith("{"):
            # Looks like a file path — resolve relative to cwd
            path = os.path.expanduser(val.strip())
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            if os.path.isfile(path):
                with open(path) as f:
                    self.google_service_account_json = f.read()
            # If file not found, leave as-is (will fail gracefully at export time)
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
