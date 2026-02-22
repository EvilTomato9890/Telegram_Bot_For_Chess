from pathlib import Path

from bot.app import create_container
from services import PairingService, TicketService, TournamentService


def test_create_container_wires_dependencies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOKEN", "token")
    monkeypatch.setenv("DB_URL", "sqlite:///db.sqlite3")
    monkeypatch.setenv("ADMIN_IDS", "10")
    monkeypatch.setenv("ARBITRS_IDS", "20")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log"))

    container = create_container()

    assert container.config.token == "token"
    assert container.config.admin_ids == [10]
    assert container.config.arbitrs_ids == [20]
    assert isinstance(container.tournament_service, TournamentService)
    assert isinstance(container.pairing_service, PairingService)
    assert isinstance(container.ticket_service, TicketService)
