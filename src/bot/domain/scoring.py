"""Scoring helpers for applying game results."""

from __future__ import annotations

from dataclasses import dataclass

from bot.domain.enums import GameResult


@dataclass(slots=True)
class ScoreDelta:
    """Score changes for white and black players after a reported result."""

    white: float
    black: float


def apply_result(result: str, *, black_player_exists: bool = True) -> ScoreDelta:
    """Convert a game result string into score delta for both players.

    Supported values: ``1-0``, ``0-1``, ``0.5-0.5``, ``bye``, ``forfeit``.
    ``forfeit`` is treated as white win by default, but if no black player exists
    (e.g. absent opponent) only white receives a point.
    """

    normalized = result.strip().lower()
    if normalized == GameResult.WHITE_WIN.value:
        return ScoreDelta(white=1.0, black=0.0)
    if normalized == GameResult.BLACK_WIN.value:
        return ScoreDelta(white=0.0, black=1.0)
    if normalized in {"0.5-0.5", "1/2-1/2", GameResult.DRAW.value.lower()}:
        return ScoreDelta(white=0.5, black=0.5)
    if normalized == GameResult.BYE.value:
        return ScoreDelta(white=1.0, black=0.0)
    if normalized == "forfeit":
        return ScoreDelta(white=1.0, black=0.0 if black_player_exists else 0.0)

    raise ValueError(f"Unsupported result value: {result}")
