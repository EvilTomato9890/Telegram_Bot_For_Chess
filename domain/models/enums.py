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
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketType(StrEnum):
    RESULT_DISPUTE = "result_dispute"
    PAIRING_ISSUE = "pairing_issue"
    TECHNICAL = "technical"
    OTHER = "other"


__all__ = [
    "TournamentStatus",
    "RoundStatus",
    "PlayerStatus",
    "TicketStatus",
    "TicketType",
]
