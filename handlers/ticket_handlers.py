"""Command handlers for ticket lifecycle."""

from __future__ import annotations

from handlers.acl import acl_required
from schemas import CloseTicketCommand, CreateTicketCommand
from services import AccessControlService, TicketService
from validators import parse_positive_int


class TicketCommandHandler:
    """Parse and handle ticket-related commands."""

    def __init__(self, ticket_service: TicketService, access_control_service: AccessControlService) -> None:
        self._ticket_service = ticket_service
        self._access_control_service = access_control_service

    @acl_required("/create_ticket")
    def handle_create_ticket(self, actor_id: int, raw_command: str) -> str:
        command = self._parse_create_ticket_command(actor_id=actor_id, raw_command=raw_command)
        ticket = self._ticket_service.create_ticket(
            ticket_type=command.ticket_type,
            author=command.actor_id,
            game_id=command.game_id,
            description=command.description,
        )
        assignee_part = f" -> assigned to {ticket.assignee_user_id}" if ticket.assignee_user_id is not None else ""
        return f"✅ ticket #{ticket.id} created ({ticket.ticket_type.value}){assignee_part}"

    @acl_required("/close_ticket")
    def handle_close_ticket(self, actor_id: int, raw_command: str) -> str:
        command = self._parse_close_ticket_command(actor_id=actor_id, raw_command=raw_command)
        ticket = self._ticket_service.close_ticket(ticket_id=command.ticket_id, closed_by=command.actor_id)
        return f"✅ ticket #{ticket.id} closed"

    def _parse_create_ticket_command(self, actor_id: int, raw_command: str) -> CreateTicketCommand:
        parts = raw_command.split(maxsplit=3)
        if len(parts) != 4:
            raise ValueError("expected format: /create_ticket <arbitr|organizer> <game_id|-> <description>")

        game_part = parts[2].strip()
        game_id = None if game_part == "-" else parse_positive_int(game_part, field_name="game_id")
        return CreateTicketCommand(
            actor_id=actor_id,
            ticket_type=parts[1],
            game_id=game_id,
            description=parts[3],
        )

    def _parse_close_ticket_command(self, actor_id: int, raw_command: str) -> CloseTicketCommand:
        parts = raw_command.split()
        if len(parts) != 2:
            raise ValueError("expected format: /close_ticket <ticket_id>")
        ticket_id = parse_positive_int(parts[1], field_name="ticket_id")
        return CloseTicketCommand(actor_id=actor_id, ticket_id=ticket_id)


__all__ = ["TicketCommandHandler"]
