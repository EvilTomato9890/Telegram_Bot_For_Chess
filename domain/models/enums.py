"""Enumerations for tournament domain statuses and ticket metadata."""

from __future__ import annotations

from enum import StrEnum


class TournamentStatus(StrEnum):
    DRAFT = "draft"
    REGISTRATION = "registration"
    ONGOING = "ongoing"
    FINISHED = "finished"


class RoundStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    FINISHED = "finished"


class PlayerStatus(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    BANNED = "banned"


class TicketStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSED = "closed"


class TicketType(StrEnum):
    ARBITR = "arbitr"
    ORGANIZER = "organizer"


__all__ = [
    "TournamentStatus",
    "RoundStatus",
    "PlayerStatus",
    "TicketStatus",
    "TicketType",
]
