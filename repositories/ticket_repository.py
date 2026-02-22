"""Ticket repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Ticket
from domain.models.enums import TicketStatus


class TicketRepository:
    """Storage adapter for tickets."""

    def __init__(self) -> None:
        self._tickets: dict[int, Ticket] = {}
        self._next_id = 1

    def add(self, ticket: Ticket) -> Ticket:
        ticket_id = self._next_id if ticket.id is None else ticket.id
        self._next_id = max(self._next_id, ticket_id + 1)
        stored = replace(ticket, id=ticket_id)
        self._tickets[ticket_id] = stored
        return stored

    def list_open(self) -> list[Ticket]:
        terminal = {TicketStatus.RESOLVED, TicketStatus.CLOSED}
        return [t for t in self._tickets.values() if t.status not in terminal]


__all__ = ["TicketRepository"]
