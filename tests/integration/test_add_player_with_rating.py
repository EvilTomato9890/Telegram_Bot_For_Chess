from domain.models import Table
from tests.utils import build_db_url, build_services


def test_add_player_by_admin_requires_and_persists_rating() -> None:
    services = build_services(build_db_url("add_player_rating"))
    registration = services["registration_service"]
    tournament_service = services["tournament_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament_service.open_registration()
    player = registration.add_player_by_admin(
        telegram_id=5001,
        username="u5001",
        full_name="Added User",
        rating=1725,
    )

    assert player.rating == 1725
    assert player.full_name == "Added User"
