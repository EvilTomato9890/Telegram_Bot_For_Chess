"""Tournament repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Tournament


class TournamentRepository:
    """Storage adapter for tournaments."""

    def __init__(self) -> None:
        self._tournaments: dict[int, Tournament] = {}
        self._next_id = 1

    def add(self, tournament: Tournament) -> Tournament:
        tournament_id = self._next_id if tournament.id is None else tournament.id
        self._next_id = max(self._next_id, tournament_id + 1)
        stored = replace(tournament, id=tournament_id)
        self._tournaments[tournament_id] = stored
        return stored

    def update(self, tournament: Tournament) -> Tournament:
        if tournament.id is None:
            raise ValueError("tournament.id is required for update")
        self._tournaments[tournament.id] = tournament
        return tournament

    def get(self, tournament_id: int) -> Tournament | None:
        return self._tournaments.get(tournament_id)


__all__ = ["TournamentRepository"]
