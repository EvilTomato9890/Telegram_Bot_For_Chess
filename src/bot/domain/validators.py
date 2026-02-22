"""Domain invariants for tournament lifecycle transitions."""

from __future__ import annotations

from bot.domain.enums import RoundStatus, TournamentStatus


class InvariantViolationError(ValueError):
    """Raised when an operation violates tournament invariants."""


def validate_can_generate_round(*, current_round_status: RoundStatus | None) -> None:
    """Ensure new round can be generated only after previous round is closed."""
    if current_round_status in {RoundStatus.SCHEDULED, RoundStatus.ACTIVE}:
        raise InvariantViolationError("Cannot generate a new round while current round is not finished")


def validate_can_finish_tournament(
    *,
    tournament_status: TournamentStatus,
    has_unfinished_rounds: bool,
    has_pending_games: bool,
) -> None:
    """Ensure tournament is completed only from a consistent state."""
    if tournament_status != TournamentStatus.ACTIVE:
        raise InvariantViolationError("Tournament can be finished only from ACTIVE status")
    if has_unfinished_rounds:
        raise InvariantViolationError("Tournament has unfinished rounds")
    if has_pending_games:
        raise InvariantViolationError("Tournament has pending games")
