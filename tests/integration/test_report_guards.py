import pytest

from domain.models import TournamentStatus
from tests.utils import build_db_url, build_services


def test_report_is_blocked_without_active_game() -> None:
    services = build_services(build_db_url("report_guard"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    result_service = services["result_service"]
    tournament_repo = services["tournament_repo"]

    tournament_service.create_tournament()
    tournament_service.open_registration()
    registration_service.register(5001, "u1", "Player One", 1200)
    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=0,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )

    with pytest.raises(ValueError, match="Нет активной партии для /report."):
        result_service.submit_player_report(5001, "white")

