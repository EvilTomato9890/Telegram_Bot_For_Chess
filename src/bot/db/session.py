"""Async session factory helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a reusable async session factory bound to the application engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_dependency(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session for DI-friendly integrations."""
    async with session_factory() as session:
        yield session
