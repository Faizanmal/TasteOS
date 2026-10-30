"""Application settings validated at startup."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TasteOSMode = Literal["demo", "live"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    tasteos_mode: TasteOSMode = Field(default="demo", alias="TASTEOS_MODE")

    qloo_api_key: str = Field(default="", alias="QLOO_API_KEY")
    qloo_base_url: str = Field(
        default="https://hackathon.api.qloo.com",
        alias="QLOO_BASE_URL",
    )
    qloo_timeout_seconds: float = Field(default=30.0, alias="QLOO_TIMEOUT_SECONDS")
    qloo_max_retries: int = Field(default=2, alias="QLOO_MAX_RETRIES")

    database_url: str = Field(
        default="postgresql+psycopg://tasteos:tasteos@localhost:5432/tasteos",
        alias="DATABASE_URL",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Render/Heroku style URLs need the async/psycopg driver prefix."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if (
            value.startswith("postgresql://")
            and "+psycopg" not in value
            and "+asyncpg" not in value
        ):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    cors_origins_extra: str = Field(
        default="",
        alias="CORS_ORIGINS",
        description="Comma-separated extra browser origins allowed for CORS",
    )
    tasteos_api_key: str = Field(default="", alias="TASTEOS_API_KEY")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    @field_validator("qloo_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def qloo_configured(self) -> bool:
        return bool(self.qloo_api_key.strip())

    @property
    def is_live_mode(self) -> bool:
        return self.tasteos_mode == "live"

    def require_live_qloo(self) -> None:
        """Raise a clear error when live mode is requested without credentials."""
        if self.is_live_mode and not self.qloo_configured:
            raise RuntimeError(
                "TASTEOS_MODE=live requires QLOO_API_KEY. "
                "Set the key from https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide "
                "or switch to TASTEOS_MODE=demo."
            )

    def cors_origins(self) -> list[str]:
        origins = {self.frontend_url.rstrip("/")}
        for part in self.cors_origins_extra.split(","):
            cleaned = part.strip().rstrip("/")
            if cleaned:
                origins.add(cleaned)
        if self.app_env == "development":
            origins.update(
                {
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                }
            )
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.require_live_qloo()
    return settings
