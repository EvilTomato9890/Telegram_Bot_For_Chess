import pytest

from domain.models import Table
from tests.utils import build_db_url, build_services


def test_prepare_stage_exposes_preview_but_blocks_report() -> None:
    services = build_services(build_db_url("prepared_access"))
    tournament_service = services["tournament_service"]
    pairing_service = services["pairing_service"]
    registration_service = services["registration_service"]
    result_service = services["result_service"]
    table_repo = services["table_repo"]
    player_repo = services["player_repo"]
    tournament_repo = services["tournament_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    p1 = registration_service.register(8101, "u1", "A", 1600)
    p2 = registration_service.register(8102, "u2", "B", 1550)
    registration_service.register(8103, "u3", "C", 1500)
    registration_service.register(8104, "u4", "D", 1450)

    tournament_service.prepare_tournament()
    preview = pairing_service.prepare_next_round_preview(1, 9001)
    assert len(preview.games) == 2

    tournament = tournament_repo.get()
    assert tournament is not None
    assert tournament.pending_pairing_payload is not None

    p1_after = player_repo.get_by_id(p1.id or 0)
    p2_after = player_repo.get_by_id(p2.id or 0)
    assert p1_after is not None
    assert p2_after is not None
    assert p1_after.seat_hint is not None
    assert p2_after.seat_hint is not None

    with pytest.raises(ValueError, match=r"Нет активной партии для /report\."):
        result_service.ensure_reportable_game(8101)

