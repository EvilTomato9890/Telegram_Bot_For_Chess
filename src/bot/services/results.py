"""Result normalization helpers."""

from __future__ import annotations

from enum import Enum


class MatchResult(str, Enum):
    """Supported user-facing result values."""

    WHITE_WIN = "1-0"
    DRAW = "1/2-1/2"
    BLACK_WIN = "0-1"
