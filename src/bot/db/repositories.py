"""Repository layer for persistence operations.

Repositories isolate SQLAlchemy statements from services and handlers to keep
application workflows testable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Player, Tournament


class TournamentRepository:
    """Persistence operations for tournament entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, title: str, rounds_total: int) -> Tournament:
        """Create and persist a new tournament."""
        tournament = Tournament(title=title, rounds_total=rounds_total)
        self._session.add(tournament)
        await self._session.commit()
        await self._session.refresh(tournament)
        return tournament

    async def get(self, tournament_id: int) -> Tournament | None:
        """Find a tournament by primary key."""
        stmt = select(Tournament).where(Tournament.id == tournament_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class PlayerRepository:
    """Persistence operations for player entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_player(
        self,
        tournament_id: int,
        telegram_id: int,
        full_name: str,
        rating: int,
    ) -> Player:
        """Register a player in the tournament."""
        player = Player(
            tournament_id=tournament_id,
            telegram_id=telegram_id,
            full_name=full_name,
            rating=rating,
        )
        self._session.add(player)
        await self._session.commit()
        await self._session.refresh(player)
        return player
