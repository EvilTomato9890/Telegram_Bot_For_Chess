"""Domain enums shared between ORM and business logic."""

from __future__ import annotations

from enum import StrEnum


class TournamentStatus(StrEnum):
    """Tournament lifecycle statuses."""

    DRAFT = "draft"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELED = "canceled"


class PlayerStatus(StrEnum):
    """Player participation statuses."""

    REGISTERED = "registered"
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"


class RoundStatus(StrEnum):
    """Round lifecycle statuses."""

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    FINISHED = "finished"


class GameStatus(StrEnum):
    """Game lifecycle statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELED = "canceled"


class GameResult(StrEnum):
    """Possible game results."""

    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "1/2-1/2"
    BYE = "bye"

