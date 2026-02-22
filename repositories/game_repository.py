"""Game repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Game


class GameRepository:
    """Storage adapter for games."""

    def __init__(self) -> None:
        self._games: dict[int, Game] = {}
        self._next_id = 1

    def add(self, game: Game) -> Game:
        game_id = self._next_id if game.id is None else game.id
        self._next_id = max(self._next_id, game_id + 1)
        stored = replace(game, id=game_id)
        self._games[game_id] = stored
        return stored

    def list_by_round(self, round_id: int) -> list[Game]:
        return [g for g in self._games.values() if g.round_id == round_id]

    def get(self, game_id: int) -> Game | None:
        return self._games.get(game_id)

    def update(self, game: Game) -> Game:
        if game.id is None:
            raise ValueError("game.id is required for update")
        self._games[game.id] = game
        return game


__all__ = ["GameRepository"]
