"""Player repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Player


class PlayerRepository:
    """Storage adapter for players."""

    def __init__(self) -> None:
        self._players: dict[int, Player] = {}
        self._next_id = 1

    def add(self, player: Player) -> Player:
        player_id = self._next_id if player.id is None else player.id
        self._next_id = max(self._next_id, player_id + 1)
        stored = replace(player, id=player_id)
        self._players[player_id] = stored
        return stored

    def update(self, player: Player) -> Player:
        if player.id is None:
            raise ValueError("player.id is required for update")
        self._players[player.id] = player
        return player

    def get(self, player_id: int) -> Player | None:
        return self._players.get(player_id)

    def list_by_tournament(self, tournament_id: int) -> list[Player]:
        return [p for p in self._players.values() if p.tournament_id == tournament_id]


__all__ = ["PlayerRepository"]
