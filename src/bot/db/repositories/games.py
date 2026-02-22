"""Repository for games."""

from __future__ import annotations

from sqlalchemy import select

from bot.db.models import Game
from bot.domain.enums import GameResult, GameStatus

from .base import Repository


class GameRepository(Repository):
    """CRUD operations for games."""

    async def create(
        self,
        round_id: int,
        board_no: int,
        white_player_id: int,
        black_player_id: int | None,
        table_id: int | None = None,
    ) -> Game:
        entity = Game(
            round_id=round_id,
            board_no=board_no,
            white_player_id=white_player_id,
            black_player_id=black_player_id,
            table_id=table_id,
        )
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get(self, game_id: int) -> Game | None:
        return await self._session.get(Game, game_id)

    async def list_by_round(self, round_id: int) -> list[Game]:
        result = await self._session.execute(select(Game).where(Game.round_id == round_id))
        return list(result.scalars().all())

    async def set_result(self, game_id: int, result: GameResult, status: GameStatus = GameStatus.FINISHED) -> Game | None:
        entity = await self.get(game_id)
        if entity is None:
            return None
        entity.result = result
        entity.status = status
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, game_id: int) -> bool:
        entity = await self.get(game_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        await self._session.commit()
        return True
