import pytest

from domain.models import Table, TournamentStatus
from tests.utils import build_db_url, build_services


def test_self_registration_precheck_fails_when_registration_closed() -> None:
    services = build_services(build_db_url("register_precheck_closed"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]

    tournament_service.create_tournament()
    with pytest.raises(ValueError, match="Регистрация закрыта"):
        registration.validate_self_registration_precheck(12345)


def test_capacity_limit_ignores_disqualified_players() -> None:
    services = build_services(build_db_url("register_precheck_dq_capacity"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament_service.open_registration()
    p1 = registration.register(1001, "u1", "A", 1500)
    p2 = registration.register(1002, "u2", "B", 1400)
    registration.disqualify(p2.id or 0)

    registration.validate_self_registration_precheck(1003)
    p3 = registration.register(1003, "u3", "C", 1300)
    assert p1.id == 1
    assert p3.id == 3


def test_self_registration_precheck_fails_without_tables() -> None:
    services = build_services(build_db_url("register_precheck_no_tables"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]

    tournament_service.create_tournament()
    tournament_service.open_registration()

    with pytest.raises(ValueError, match="без столов"):
        registration.validate_self_registration_precheck(9999)


def test_admin_precheck_blocks_changes_after_start() -> None:
    services = build_services(build_db_url("register_precheck_admin"))
    registration = services["registration_service"]
    tournament_repo = services["tournament_repo"]
    tournament_service = services["tournament_service"]

    tournament = tournament_service.create_tournament()
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=tournament.number_of_rounds,
        current_round=tournament.current_round,
        rules_text=tournament.rules_text,
        pending_pairing_payload=tournament.pending_pairing_payload,
    )

    with pytest.raises(ValueError, match="Добавление игроков доступно только до старта турнира"):
        registration.validate_admin_add_precheck()
