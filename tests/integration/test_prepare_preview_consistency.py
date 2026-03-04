from domain.models import Table
from tests.utils import build_db_url, build_services


def test_prepare_preview_matches_first_started_round() -> None:
    services = build_services(build_db_url("prepare_preview"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    pairing_service = services["pairing_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    tournament_service.set_round_number(3, confirm=True)
    registration_service.register(1001, "u1", "A", 1700)
    registration_service.register(1002, "u2", "B", 1600)
    registration_service.register(1003, "u3", "C", 1500)
    registration_service.register(1004, "u4", "D", 1400)

    tournament_service.prepare_tournament()
    preview = pairing_service.prepare_next_round_preview(1, 9001)
    assert preview.needs_confirmation is False

    tournament_service.start_tournament()
    started = pairing_service.generate_next_round(1, 9001, force=False)

    preview_pairs = {(g.board_number, g.white_player_id, g.black_player_id) for g in preview.games}
    started_pairs = {(g.board_number, g.white_player_id, g.black_player_id) for g in started.games if not g.is_bye}
    assert preview_pairs == started_pairs

