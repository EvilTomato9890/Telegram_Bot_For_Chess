"""Repository for rounds."""

from __future__ import annotations

from sqlalchemy import select

from bot.db.models import Round
from bot.domain.enums import RoundStatus

from .base import Repository


class RoundRepository(Repository):
    """CRUD operations for rounds."""

    async def create(self, tournament_id: int, number: int) -> Round:
        entity = Round(tournament_id=tournament_id, number=number)
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, round_id: int) -> Round | None:
        return await self._session.get(Round, round_id)

    async def list_by_tournament(self, tournament_id: int) -> list[Round]:
        result = await self._session.execute(
            select(Round).where(Round.tournament_id == tournament_id).order_by(Round.number.asc())
        )
        return list(result.scalars().all())

    async def update_status(self, round_id: int, status: RoundStatus) -> Round | None:
        entity = await self.get(round_id)
        if entity is None:
            return None
        entity.status = status
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, round_id: int) -> bool:
        entity = await self.get(round_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        await self._session.commit()
        return True
