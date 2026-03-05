"""Service response DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import Game


@dataclass(frozen=True, slots=True)
class PairingOutcome:
    """Round generation result with optional admin confirmation demand."""

    round_number: int
    games: tuple[Game, ...]
    bye_player_id: int | None
    needs_confirmation: bool
    confirmation_reason: str | None


@dataclass(frozen=True, slots=True)
class ReportOutcome:
    """Result of player report submission."""

    game_id: int
    status: str
    message: str
    confirmed_result: str | None = None
    white_telegram_id: int | None = None
    black_telegram_id: int | None = None
    round_closed: bool = False
    round_number: int | None = None
    next_round_hint: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveOutcome:
    """Result of arbiter/admin result approval."""

    game_id: int
    confirmed_result: str
    message: str
    white_telegram_id: int | None = None
    black_telegram_id: int | None = None
    round_closed: bool = False
    round_number: int | None = None
    next_round_hint: str | None = None
    reseed_required: bool = False
