"""Domain enum types for roles, statuses and game outcomes."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """User role used by ACL checks."""

    PLAYER = "player"
    ARBITRATOR = "arbitrator"
    ORGANIZER = "organizer"


class TournamentStatus(StrEnum):
    """Lifecycle states for the only tournament in the system."""

    DRAFT = "draft"
    REGISTRATION = "registration"
    ONGOING = "ongoing"
    FINISHED = "finished"


class RoundStatus(StrEnum):
    """Lifecycle states for one round."""

    GENERATED = "generated"
    ONGOING = "ongoing"
    CLOSED = "closed"


class PlayerStatus(StrEnum):
    """Player availability for future pairings."""

    ACTIVE = "active"
    DISQUALIFIED = "disqualified"


class TicketStatus(StrEnum):
    """Ticket lifecycle for arbitration/organizer requests."""

    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSED = "closed"


class TicketType(StrEnum):
    """Ticket route target."""

    ARBITR = "arbitr"
    ORGANIZER = "organizer"


class GameResult(StrEnum):
    """Canonical game outcomes stored in DB."""

    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "0.5-0.5"
    BYE = "bye"
    FORFEIT = "forfeit"


__all__ = [
    "Role",
    "TournamentStatus",
    "RoundStatus",
    "PlayerStatus",
    "TicketStatus",
    "TicketType",
    "GameResult",
]
