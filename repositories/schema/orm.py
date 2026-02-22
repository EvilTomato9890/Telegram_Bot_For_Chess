"""Persistence-layer models mirroring database tables."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import PlayerStatus, RoundStatus, TicketStatus, TicketType, TournamentStatus


@dataclass(slots=True)
class TournamentORM:
    id: int
    name: str
    status: TournamentStatus
    created_at: str


@dataclass(slots=True)
class PlayerORM:
    id: int
    tournament_id: int
    telegram_user_id: int
    display_name: str
    status: PlayerStatus
    score: float
    buchholz: float
    median_buchholz: float
    sonneborn_berger: float


@dataclass(slots=True)
class RoundORM:
    id: int
    tournament_id: int
    number: int
    status: RoundStatus


@dataclass(slots=True)
class TableORM:
    id: int
    round_id: int
    number: int


@dataclass(slots=True)
class SeatORM:
    id: int
    table_id: int
    player_id: int
    color: str


@dataclass(slots=True)
class GameORM:
    id: int
    round_id: int
    table_id: int | None
    white_player_id: int
    black_player_id: int
    result: str | None


@dataclass(slots=True)
class TicketORM:
    id: int
    author_player_id: int
    ticket_type: TicketType
    status: TicketStatus
    game_id: int | None
    title: str
    body: str


__all__ = [
    "TournamentORM",
    "PlayerORM",
    "RoundORM",
    "TableORM",
    "SeatORM",
    "GameORM",
    "TicketORM",
]
