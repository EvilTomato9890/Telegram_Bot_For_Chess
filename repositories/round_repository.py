"""Round repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Round


class RoundRepository:
    """Storage adapter for rounds."""

    def __init__(self) -> None:
        self._rounds: dict[int, Round] = {}
        self._next_id = 1

    def add(self, round_: Round) -> Round:
        round_id = self._next_id if round_.id is None else round_.id
        self._next_id = max(self._next_id, round_id + 1)
        stored = replace(round_, id=round_id)
        self._rounds[round_id] = stored
        return stored

    def list_by_tournament(self, tournament_id: int) -> list[Round]:
        return [r for r in self._rounds.values() if r.tournament_id == tournament_id]


__all__ = ["RoundRepository"]
