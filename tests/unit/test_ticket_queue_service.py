from domain.models import TicketType
from tests.utils import build_db_url, build_services


def test_arbitrator_queue_returns_relevant_active_tickets() -> None:
    services = build_services(build_db_url("ticket_queue"))
    ticket_service = services["ticket_service"]
    t1 = ticket_service.create_ticket(actor_id=100, ticket_type=TicketType.ARBITR, description="conflict #1")
    t2 = ticket_service.create_ticket(actor_id=101, ticket_type=TicketType.ARBITR, description="conflict #2")
    ticket_service.create_ticket(actor_id=102, ticket_type=TicketType.ORGANIZER, description="org-only")
    ticket_service.close_ticket(actor_id=t1.assignee_telegram_id or 9002, ticket_id=t1.id)

    queue_for_arb = ticket_service.ticket_queue_for_arbitrator(9002)
    ids = {ticket.id for ticket in queue_for_arb}
    assert t2.id in ids
    assert t1.id not in ids
    assert all(ticket.ticket_type == TicketType.ARBITR for ticket in queue_for_arb)


def test_admin_can_see_full_arbitrator_queue() -> None:
    services = build_services(build_db_url("ticket_queue_admin"))
    ticket_service = services["ticket_service"]

    t1 = ticket_service.create_ticket(actor_id=201, ticket_type=TicketType.ARBITR, description="game A")
    t2 = ticket_service.create_ticket(actor_id=202, ticket_type=TicketType.ARBITR, description="game B")
    queue_for_admin = ticket_service.ticket_queue_for_arbitrator(9001)
    ids = {ticket.id for ticket in queue_for_admin}
    assert t1.id in ids
    assert t2.id in ids
