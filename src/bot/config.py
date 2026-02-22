"""Application settings loader.

This module centralizes configuration parsing from environment variables to keep
infrastructure concerns out of business logic and handlers.
"""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime configuration read from `.env` and environment.

    Attributes:
        token: Telegram bot token used by aiogram.
        admin_ids: Telegram user IDs with organizer permissions.
        timezone: IANA timezone name used for tournament scheduling.
        database_url: SQLAlchemy connection string.
        log_level: Minimal logging level for structured logs.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token: str = Field(alias="TOKEN")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    timezone: str = Field(default="UTC", alias="TIMEZONE")
    database_url: str = Field(default="sqlite+aiosqlite:///./tournaments.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        """Parse comma-separated admin IDs from `.env` into integers."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        raise ValueError("ADMIN_IDS must be a comma-separated string or list")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Validate timezone early to avoid runtime scheduling errors."""
        ZoneInfo(value)
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated env parsing."""
    return Settings()
