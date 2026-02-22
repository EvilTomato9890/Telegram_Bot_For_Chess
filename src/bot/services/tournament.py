"""Application service orchestrating tournament use-cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Sequence

if TYPE_CHECKING:
    from bot.db.repositories import PlayerRepository, TournamentRepository
from bot.domain.swiss import Standing, sort_standings, swiss_pairings


class TableLike(Protocol):
    """Minimal table projection required for pairing assignments."""

    id: int
    number: int
    is_active: bool


class InsufficientTablesError(ValueError):
    """Raised when round generation requires more tables than available."""


@dataclass(slots=True)
class PairingAssignment:
    """Pairing mapped to a sequential board and physical table."""

    board_no: int
    table_id: int
    table_number: int
    white_player_id: int
    black_player_id: int


class TournamentService:
    """High-level operations for tournament workflows."""

    def __init__(self, tournaments: "TournamentRepository" | Any, players: "PlayerRepository" | Any) -> None:
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

    def assign_tables(
        self,
        pairings: Sequence[tuple[int, int | None]],
        tables: Sequence[TableLike],
    ) -> list[PairingAssignment]:
        """Assign sequential board numbers and table ids to non-bye pairings."""
        games = [(white_id, black_id) for white_id, black_id in pairings if black_id is not None]
        active_tables = sorted((table for table in tables if table.is_active), key=lambda table: table.number)

        if len(active_tables) < len(games):
            raise InsufficientTablesError(
                "Недостаточно столов для генерации тура. Добавьте столы и повторите команду."
            )

        assignments: list[PairingAssignment] = []
        for board_no, ((white_id, black_id), table) in enumerate(zip(games, active_tables, strict=True), start=1):
            assignments.append(
                PairingAssignment(
                    board_no=board_no,
                    table_id=table.id,
                    table_number=board_no,
                    white_player_id=white_id,
                    black_player_id=black_id,
                )
            )
        return assignments
