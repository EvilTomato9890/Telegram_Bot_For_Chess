import pytest

from domain.models import Table
from tests.utils import build_db_url, build_services


def test_prepare_counts_only_active_players() -> None:
    services = build_services(build_db_url("dq_capacity_prepare"))
    tournament_service = services["tournament_service"]
    registration = services["registration_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)

    p1 = registration.register(5201, "u1", "A", 1500)
    p2 = registration.register(5202, "u2", "B", 1450)
    registration.disqualify(p2.id or 0)

    with pytest.raises(ValueError, match="минимум 2 активных"):
        tournament_service.prepare_tournament()

    registration.register(5203, "u3", "C", 1400)
    prepared = tournament_service.prepare_tournament()
    assert prepared.prepared is True
    assert p1.id == 1
