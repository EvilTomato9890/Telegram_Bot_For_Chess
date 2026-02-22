"""Application service orchestrating tournament use-cases."""

from __future__ import annotations

from bot.db.repositories import PlayerRepository, TournamentRepository
from bot.domain.swiss import Standing, sort_standings, swiss_pairings


class TournamentService:
    """High-level operations for tournament workflows."""

    def __init__(self, tournaments: TournamentRepository, players: PlayerRepository) -> None:
        self._tournaments = tournaments
        self._players = players

    async def create_tournament(self, rounds_count: int, rules_text: str = "") -> int:
        """Create a tournament and return its identifier for bot messaging."""
        entity = await self._tournaments.create(rounds_count=rounds_count, rules_text=rules_text)
        return entity.id

    def build_pairings(self, standings: list[Standing]) -> list[tuple[int, int | None]]:
        """Generate pairings from already computed standings."""
        ordered = sort_standings(standings)
        return swiss_pairings([entry.player_id for entry in ordered])
