import pytest

from domain.models import Role, TicketStatus, TicketType
from tests.utils import build_db_url, build_services


def test_ticket_service_assigns_least_loaded_assignee() -> None:
    services = build_services(build_db_url("ticket"))
    ticket_service = services["ticket_service"]
    role_repo = services["role_repo"]

    role_repo.append(100, Role.ARBITRATOR, "grant")
    role_repo.append(200, Role.ARBITRATOR, "grant")

    t1 = ticket_service.create_ticket(1, TicketType.ARBITR, "one")
    t2 = ticket_service.create_ticket(1, TicketType.ARBITR, "two")
    assert t1.assignee_telegram_id is not None
    assert t2.assignee_telegram_id is not None
    assert t1.assignee_telegram_id != t2.assignee_telegram_id


def test_ticket_close_without_id_closes_own_last_open() -> None:
    services = build_services(build_db_url("ticket_close"))
    ticket_service = services["ticket_service"]

    created = ticket_service.create_ticket(111, TicketType.ORGANIZER, "help")
    closed = ticket_service.close_ticket(actor_id=111, ticket_id=None)
    assert created.id == closed.id
    assert closed.status == TicketStatus.CLOSED


def test_ticket_close_by_id_requires_owner_or_privileged_role() -> None:
    services = build_services(build_db_url("ticket_acl"))
    ticket_service = services["ticket_service"]

    created = ticket_service.create_ticket(111, TicketType.ORGANIZER, "help")
    with pytest.raises(PermissionError):
        ticket_service.close_ticket(actor_id=777, ticket_id=created.id)
