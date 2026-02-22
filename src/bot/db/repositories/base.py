"""Shared repository primitives."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession


class Repository:
    """Base repository exposing shared transaction helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Open a transaction block and commit/rollback atomically."""
        async with self._session.begin():
            yield self._session
