"""Core domain entities for chess tournaments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import PlayerStatus, RoundStatus, TicketStatus, TicketType, TournamentStatus

_VALID_RESULT_POINTS = {0.0, 0.5, 1.0}


@dataclass(slots=True)
class Tournament:
    id: int | None
    name: str
    status: TournamentStatus = TournamentStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class Player:
    id: int | None
    tournament_id: int
    telegram_user_id: int
    display_name: str
    status: PlayerStatus = PlayerStatus.REGISTERED
    score: float = 0.0
    buchholz: float = 0.0
    median_buchholz: float = 0.0
    sonneborn_berger: float = 0.0

    def update_tiebreakers(self, opponents_scores: list[float], game_results: list[tuple[float, float]]) -> None:
        """Update tiebreak values based on opponents and game outcomes.

        `game_results` stores `(result_points, opponent_final_score)` tuples.
        """

        if len(opponents_scores) != len(game_results):
            raise ValueError("opponents_scores and game_results must have equal lengths")

        for score in opponents_scores:
            if score < 0:
                raise ValueError("Opponent scores must be non-negative")

        for result_points, opponent_score in game_results:
            if result_points not in _VALID_RESULT_POINTS:
                raise ValueError("Result points must be one of 0.0, 0.5, 1.0")
            if opponent_score < 0:
                raise ValueError("Opponent scores must be non-negative")

        self.buchholz = sum(opponents_scores)

        if len(opponents_scores) > 2:
            ordered = sorted(opponents_scores)
            self.median_buchholz = sum(ordered[1:-1])
        else:
            self.median_buchholz = self.buchholz

        self.sonneborn_berger = sum(result * opponent_score for result, opponent_score in game_results)


@dataclass(slots=True)
class Round:
    id: int | None
    tournament_id: int
    number: int
    status: RoundStatus = RoundStatus.PLANNED


@dataclass(slots=True)
class Table:
    id: int | None
    round_id: int
    number: int


@dataclass(slots=True)
class Seat:
    id: int | None
    table_id: int
    player_id: int
    color: str


@dataclass(slots=True)
class Game:
    id: int | None
    round_id: int
    table_id: int | None
    white_player_id: int
    black_player_id: int
    result: str | None = None


@dataclass(slots=True)
class Ticket:
    id: int | None
    author_player_id: int
    ticket_type: TicketType
    status: TicketStatus = TicketStatus.OPEN
    game_id: int | None = None
    title: str = ""
    body: str = ""


__all__ = [
    "Tournament",
    "Player",
    "Round",
    "Game",
    "Ticket",
    "Table",
    "Seat",
]
