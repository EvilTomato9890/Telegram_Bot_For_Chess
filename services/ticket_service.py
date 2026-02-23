"""Ticket creation, assignment and closure logic."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from domain.models import Role, Ticket, TicketStatus, TicketType
from infra.logging import AuditLogger
from repositories import TicketRepository

from .acl_service import AccessControlService


class TicketService:
    """Manage tickets and least-loaded assignee routing."""

    def __init__(
        self,
        ticket_repo: TicketRepository,
        acl_service: AccessControlService,
        audit_logger: AuditLogger,
    ) -> None:
        self._ticket_repo = ticket_repo
        self._acl_service = acl_service
        self._audit_logger = audit_logger

    def create_ticket(
        self,
        actor_id: int,
        ticket_type: TicketType,
        description: str,
        game_id: int | None = None,
    ) -> Ticket:
        """Create ticket and assign it to the least-loaded actor."""

        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("Описание тикета не может быть пустым.")

        target_role = Role.ARBITRATOR if ticket_type == TicketType.ARBITR else Role.ORGANIZER
        assignee = self._select_assignee(target_role)
        status = TicketStatus.ASSIGNED if assignee is not None else TicketStatus.OPEN
        ticket = self._ticket_repo.add(
            Ticket(
                id=None,
                ticket_type=ticket_type,
                author_telegram_id=actor_id,
                status=status,
                assignee_telegram_id=assignee,
                game_id=game_id,
                description=normalized_description,
                opened_at=datetime.now(UTC),
            )
        )
        self._audit_logger.log_event(
            actor_id=actor_id,
            roles=[role.value for role in self._acl_service.resolve_roles(actor_id)],
            command="/create_ticket",
            entity=f"ticket:{ticket.id}",
            before=None,
            after={"status": ticket.status.value, "assignee": ticket.assignee_telegram_id},
            result="ok",
            reason=None,
        )
        return ticket

    def close_ticket(self, actor_id: int, ticket_id: int | None = None) -> Ticket:
        """Close explicit ticket or actor's latest own open ticket."""

        actor_roles = self._acl_service.resolve_roles(actor_id)
        ticket: Ticket
        if ticket_id is None:
            own = self._ticket_repo.list_open_by_author(actor_id)
            if not own:
                raise ValueError("У вас нет открытых тикетов.")
            ticket = own[0]
        else:
            explicit_ticket = self._ticket_repo.get_by_id(ticket_id)
            if explicit_ticket is None:
                raise ValueError("Тикет не найден.")
            if not self._can_close_ticket(actor_id=actor_id, actor_roles=actor_roles, ticket=explicit_ticket):
                raise PermissionError("Недостаточно прав для закрытия этого тикета.")
            ticket = explicit_ticket

        if ticket.status == TicketStatus.CLOSED:
            raise ValueError("Тикет уже закрыт.")

        closed = replace(
            ticket,
            status=TicketStatus.CLOSED,
            closed_at=datetime.now(UTC),
            closed_by_telegram_id=actor_id,
        )
        stored = self._ticket_repo.update(closed)
        self._audit_logger.log_event(
            actor_id=actor_id,
            roles=[role.value for role in actor_roles],
            command="/close_ticket",
            entity=f"ticket:{stored.id}",
            before={"status": ticket.status.value},
            after={"status": stored.status.value},
            result="ok",
            reason=None,
        )
        return stored

    def _select_assignee(self, role: Role) -> int | None:
        candidates = self._acl_service.user_ids_with_role(role)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda candidate: (
                self._ticket_repo.active_stats_for_assignee(candidate)[0],
                self._ticket_repo.active_stats_for_assignee(candidate)[1],
                candidate,
            ),
        )

    @staticmethod
    def _can_close_ticket(*, actor_id: int, actor_roles: set[Role], ticket: Ticket) -> bool:
        """Check ACL for explicit ticket closure."""

        if ticket.author_telegram_id == actor_id:
            return True
        if Role.ORGANIZER in actor_roles:
            return True
        if Role.ARBITRATOR in actor_roles and ticket.ticket_type == TicketType.ARBITR:
            return True
        return False

