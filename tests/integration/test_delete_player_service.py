import pytest

from domain.models import TournamentStatus
from tests.utils import build_db_url, build_services


def test_delete_player_removes_active_and_disqualified_before_start() -> None:
    services = build_services(build_db_url("delete_player_ok"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]

    tournament_service.create_tournament()
    tournament_service.open_registration()
    p1 = registration.register(4001, "u1", "A", 1500)
    p2 = registration.register(4002, "u2", "B", 1400)
    registration.disqualify(p2.id or 0)

    removed_active = registration.delete_player_by_admin(p1.id or 0)
    removed_dq = registration.delete_player_by_admin(p2.id or 0)

    assert removed_active.full_name == "A"
    assert removed_dq.full_name == "B"
    assert services["player_repo"].get_by_id(p1.id or 0) is None
    assert services["player_repo"].get_by_id(p2.id or 0) is None


def test_delete_player_blocked_after_start() -> None:
    services = build_services(build_db_url("delete_player_blocked"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]
    tournament_repo = services["tournament_repo"]

    tournament = tournament_service.create_tournament()
    tournament_service.open_registration()
    player = registration.register(4101, "u1", "A", 1500)
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=tournament.number_of_rounds,
        current_round=tournament.current_round,
        rules_text=tournament.rules_text,
        pending_pairing_payload=tournament.pending_pairing_payload,
    )

    with pytest.raises(ValueError, match="Удалять игрока можно только до старта турнира"):
        registration.delete_player_by_admin(player.id or 0)
