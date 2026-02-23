from pathlib import Path

import pytest

from handlers import TicketCommandHandler
from infra.logging import setup_logging
from repositories import TicketRepository
from services import AccessControlService, TicketService


@pytest.fixture
def ticket_handler(tmp_path: Path) -> TicketCommandHandler:
    access = AccessControlService(config_roles_by_user={1: {"player"}, 2: {"arbiter"}, 9: {"admin"}})
    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=setup_logging(audit_log_path=str(tmp_path / "audit.log")),
        arbitrs_ids=[2],
        organizer_ids=[9],
    )
    return TicketCommandHandler(ticket_service=service, access_control_service=access)


def test_create_ticket_command(ticket_handler: TicketCommandHandler) -> None:
    message = ticket_handler.handle_create_ticket(
        actor_id=1,
        raw_command="/create_ticket arbitr 100 result mismatch",
    )

    assert "ticket #1 created" in message
    assert "assigned to 2" in message


def test_close_ticket_command(ticket_handler: TicketCommandHandler) -> None:
    ticket_handler.handle_create_ticket(actor_id=1, raw_command="/create_ticket organizer - scheduling question")

    message = ticket_handler.handle_close_ticket(actor_id=9, raw_command="/close_ticket 1")

    assert "ticket #1 closed" in message


def test_close_ticket_requires_acl(ticket_handler: TicketCommandHandler) -> None:
    ticket_handler.handle_create_ticket(actor_id=1, raw_command="/create_ticket organizer - scheduling question")

    with pytest.raises(PermissionError, match="access denied"):
        ticket_handler.handle_close_ticket(actor_id=1, raw_command="/close_ticket 1")
