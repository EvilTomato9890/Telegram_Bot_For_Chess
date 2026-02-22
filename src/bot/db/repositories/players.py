"""Repository for player entities."""

from __future__ import annotations

from sqlalchemy import select

from bot.db.models import Player
from bot.domain.enums import PlayerStatus

from .base import Repository


class PlayerRepository(Repository):
    """CRUD operations for players."""

    async def create(
        self,
        tournament_id: int,
        telegram_id: int,
        display_name: str,
        username: str | None = None,
    ) -> Player:
        entity = Player(
            tournament_id=tournament_id,
            telegram_id=telegram_id,
            display_name=display_name,
            username=username,
        )
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, player_id: int) -> Player | None:
        return await self._session.get(Player, player_id)

    async def list_by_tournament(self, tournament_id: int) -> list[Player]:
        result = await self._session.execute(select(Player).where(Player.tournament_id == tournament_id))
        return list(result.scalars().all())

    async def update_status(self, player_id: int, status: PlayerStatus) -> Player | None:
        entity = await self.get(player_id)
        if entity is None:
            return None
        entity.status = status
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, player_id: int) -> bool:
        entity = await self.get(player_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        await self._session.commit()
        return True
