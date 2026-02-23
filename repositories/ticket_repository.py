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

    def get(self, ticket_id: int) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def update(self, ticket: Ticket) -> Ticket:
        if ticket.id is None:
            raise ValueError("ticket id is required")
        self._tickets[ticket.id] = ticket
        return ticket

    def list_active(self) -> list[Ticket]:
        active_statuses = {TicketStatus.OPEN, TicketStatus.ASSIGNED}
        return [t for t in self._tickets.values() if t.status in active_statuses]

    def active_count_by_assignee(self, assignee_user_id: int) -> int:
        return sum(
            1
            for ticket in self.list_active()
            if ticket.assignee_user_id == assignee_user_id
        )


__all__ = ["TicketRepository"]
