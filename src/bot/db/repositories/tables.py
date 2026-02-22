"""Repository for tables."""

from __future__ import annotations

from sqlalchemy import select

from bot.db.models import Table

from .base import Repository


class TableRepository(Repository):
    """CRUD operations for tables."""

    async def create(self, number: int, location: str | None = None, is_active: bool = True) -> Table:
        entity = Table(number=number, location=location, is_active=is_active)
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, table_id: int) -> Table | None:
        return await self._session.get(Table, table_id)

    async def list(self) -> list[Table]:
        result = await self._session.execute(select(Table).order_by(Table.number.asc()))
        return list(result.scalars().all())

    async def update(self, table_id: int, location: str | None, is_active: bool) -> Table | None:
        entity = await self.get(table_id)
        if entity is None:
            return None
        entity.location = location
        entity.is_active = is_active
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, table_id: int) -> bool:
        entity = await self.get(table_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        await self._session.commit()
        return True
