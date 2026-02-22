"""Database engine setup for async SQLAlchemy access."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    The engine is created in a dedicated helper to simplify testing and
    environment-specific overrides.
    """
    return create_async_engine(database_url, echo=False, future=True)
