"""Service response DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import Game


@dataclass(frozen=True, slots=True)
class PairingOutcome:
    """Round generation result with optional organizer confirmation demand."""

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

