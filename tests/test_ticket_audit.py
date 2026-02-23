from pathlib import Path

from infra.logging import setup_logging
from repositories import TicketRepository
from services import TicketService


def test_ticket_audit_log_contains_create_assignment_and_close_metadata(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"
    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=setup_logging(audit_log_path=str(log_path)),
        arbitrs_ids=[2],
        organizer_ids=[9],
    )

    ticket = service.create_ticket(ticket_type="arbitr", author=1, game_id=11, description="mismatch")
    service.close_ticket(ticket_id=ticket.id or 0, closed_by=2)

    content = log_path.read_text(encoding="utf-8")
    assert "actor=1" in content
    assert "command=/create_ticket" in content
    assert "assignee=2" in content
    assert "actor=2" in content
    assert "command=/close_ticket" in content
    assert "action=closed" in content
