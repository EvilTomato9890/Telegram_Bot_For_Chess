from domain.models import TournamentStatus
from tests.utils import build_db_url, build_services
import pytest


def test_prepare_tournament_reports_missing_preconditions() -> None:
    services = build_services(build_db_url("prepare_missing"))
    tournament_service = services["tournament_service"]

    tournament_service.create_tournament(1)
    tournament_service.open_registration()

    with pytest.raises(ValueError) as exc:
        tournament_service.prepare_tournament()

    message = str(exc.value)
    assert "Подготовка невозможна" in message
    assert "не задано число туров" in message
    assert "нужно минимум 2 активных участника" in message


def test_prepare_tournament_fails_when_tables_are_not_enough() -> None:
    services = build_services(build_db_url("prepare_tables"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament(2)
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    registration_service.register(1001, "u1", "A", 1500)
    registration_service.register(1002, "u2", "B", 1450)
    registration_service.register(1003, "u3", "C", 1400)
    registration_service.register(1004, "u4", "D", 1350)
    assert table_repo.remove_by_number(2) is True

    with pytest.raises(ValueError) as exc:
        tournament_service.prepare_tournament()

    message = str(exc.value)
    assert "Подготовка невозможна" in message
    assert "вместимость" in message
    assert "недостаточно столов" in message


def test_prepare_tournament_succeeds_when_ready() -> None:
    services = build_services(build_db_url("prepare_ok"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]

    tournament_service.create_tournament(2)
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    registration_service.register(2001, "v1", "A", 1500)
    registration_service.register(2002, "v2", "B", 1450)
    registration_service.register(2003, "v3", "C", 1400)
    registration_service.register(2004, "v4", "D", 1350)

    prepared = tournament_service.prepare_tournament()
    assert prepared.prepared is True
    assert prepared.status == TournamentStatus.REGISTRATION
