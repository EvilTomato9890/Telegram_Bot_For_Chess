import pytest

from domain.models import Table, TournamentStatus
from tests.utils import build_db_url, build_services


def test_open_registration_blocks_when_active_players_exceed_capacity() -> None:
    services = build_services(build_db_url("open_registration_capacity"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    registration_service.add_player_by_admin(
        telegram_id=12345,
        username=None,
        full_name="Player One",
        rating=1500,
    )
    assert table_repo.remove_by_number(1) is True

    with pytest.raises(ValueError):
        tournament_service.open_registration()

    assert tournament_service.ensure_tournament().status == TournamentStatus.DRAFT


def test_open_registration_allows_empty_roster_without_tables() -> None:
    services = build_services(build_db_url("open_registration_empty"))
    tournament_service = services["tournament_service"]

    tournament_service.create_tournament()
    tournament = tournament_service.open_registration()
    assert tournament.status == TournamentStatus.REGISTRATION
