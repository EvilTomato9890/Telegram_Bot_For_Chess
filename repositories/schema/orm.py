"""Optional simple typed row containers for SQLite adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TournamentORM:
    id: int
    status: str
    number_of_rounds: int
    current_round: int
    rules_text: str
    prepared: int
    pending_pairing_payload: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class PlayerORM:
    id: int
    telegram_id: int
    username: str | None
    full_name: str
    rating: int
    status: str
    score: float
    buchholz: float
    median_buchholz: float
    sonneborn_berger: float
    had_bye: int
    current_board: int | None
    seat_hint: str | None
    created_at: str


@dataclass(slots=True)
class RoundORM:
    id: int
    number: int
    status: str
    starts_at: str | None
    window_end_at: str | None
    generated_at: str
    closed_at: str | None


@dataclass(slots=True)
class TableORM:
    id: int
    number: int
    location: str
    place_hint: str | None


@dataclass(slots=True)
class GameORM:
    id: int
    round_id: int
    board_number: int
    white_player_id: int
    black_player_id: int
    result: str | None
    result_source: str | None
    is_bye: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class TicketORM:
    id: int
    type: str
    author_telegram_id: int
    status: str
    assignee_telegram_id: int | None
    game_id: int | None
    description: str
    opened_at: str
    closed_at: str | None
    closed_by_telegram_id: int | None


__all__ = ["TournamentORM", "PlayerORM", "RoundORM", "TableORM", "GameORM", "TicketORM"]
