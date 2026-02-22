"""Database initialization and migration helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config


_migration_lock = asyncio.Lock()


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url.replace("sqlite+aiosqlite://", "sqlite+pysqlite://", 1)
    return database_url


def _build_alembic_config(database_url: str) -> Config:
    project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", _sync_database_url(database_url))
    return config


async def initialize_database(database_url: str) -> None:
    """Run pending migrations once in a safe, idempotent way."""
    async with _migration_lock:
        config = _build_alembic_config(database_url)
        await asyncio.to_thread(command.upgrade, config, "head")
