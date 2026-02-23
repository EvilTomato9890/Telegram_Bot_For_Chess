"""Service response DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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


@dataclass(frozen=True, slots=True)
class UndoResult:
    """Result payload for one applied admin undo operation."""

    snapshot_id: int
    undone_action: str
    restored_at: datetime
