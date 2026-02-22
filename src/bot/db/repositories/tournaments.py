"""Repository for tournament aggregates."""

from __future__ import annotations

from sqlalchemy import select

from bot.db.models import Tournament
from bot.domain.enums import TournamentStatus

from .base import Repository


class TournamentRepository(Repository):
    """CRUD operations for tournaments."""

    async def create(self, rounds_count: int, rules_text: str = "") -> Tournament:
        entity = Tournament(rounds_count=rounds_count, rules_text=rules_text)
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, tournament_id: int) -> Tournament | None:
        return await self._session.get(Tournament, tournament_id)

    async def list(self) -> list[Tournament]:
        result = await self._session.execute(select(Tournament).order_by(Tournament.id.asc()))
        return list(result.scalars().all())

    async def update_status(self, tournament_id: int, status: TournamentStatus) -> Tournament | None:
        entity = await self.get(tournament_id)
        if entity is None:
            return None
        entity.status = status
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, tournament_id: int) -> bool:
        entity = await self.get(tournament_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        await self._session.commit()
        return True
