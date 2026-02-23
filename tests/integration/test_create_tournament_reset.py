from domain.models import Table
from tests.utils import build_db_url, build_services


def test_create_tournament_resets_autoincrement_for_players() -> None:
    services = build_services(build_db_url("create_reset"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament_service.open_registration()
    p1 = registration_service.register(101, "u1", "A", 1500)
    p2 = registration_service.register(102, "u2", "B", 1400)
    assert p1.id == 1
    assert p2.id == 2

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament_service.open_registration()
    p3 = registration_service.register(103, "u3", "C", 1300)
    assert p3.id == 1

