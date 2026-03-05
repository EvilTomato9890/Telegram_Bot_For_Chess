"""Core domain entities for the Swiss tournament bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import GameResult, PlayerStatus, RoundStatus, TicketStatus, TicketType, TournamentStatus


@dataclass(slots=True)
class Tournament:
    """The only tournament in the application."""

    id: int = 1
    status: TournamentStatus = TournamentStatus.DRAFT
    number_of_rounds: int = 0
    current_round: int = 0
    rules_text: str = ""
    prepared: bool = False
    pending_pairing_payload: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Player:
    """A registered participant."""

    id: int | None
    telegram_id: int
    username: str | None
    full_name: str
    rating: int
    status: PlayerStatus = PlayerStatus.ACTIVE
    score: float = 0.0
    buchholz: float = 0.0
    median_buchholz: float = 0.0
    sonneborn_berger: float = 0.0
    had_bye: bool = False
    current_board: int | None = None
    seat_hint: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Round:
    """One tournament round."""

    id: int | None
    number: int
    status: RoundStatus = RoundStatus.GENERATED
    starts_at: datetime | None = None
    window_end_at: datetime | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None


@dataclass(slots=True)
class Table:
    """Physical board location description."""

    id: int | None
    number: int
    location: str
    place_hint: str | None = None


@dataclass(slots=True)
class Game:
    """One pairing game in a round."""

    id: int | None
    round_id: int
    board_number: int
    white_player_id: int
    black_player_id: int
    result: GameResult | None = None
    result_source: str | None = None
    is_bye: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class GameReport:
    """One player's report for a game."""

    id: int | None
    game_id: int
    reporter_player_id: int
    reported_result: GameResult
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Ticket:
    """Ticket to call arbitrator/organizer."""

    id: int | None
    ticket_type: TicketType
    author_telegram_id: int
    status: TicketStatus = TicketStatus.OPEN
    assignee_telegram_id: int | None = None
    game_id: int | None = None
    description: str = ""
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    closed_by_telegram_id: int | None = None


__all__ = [
    "Tournament",
    "Player",
    "Round",
    "Table",
    "Game",
    "GameReport",
    "Ticket",
]
