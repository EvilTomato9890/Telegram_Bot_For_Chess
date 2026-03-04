from datetime import UTC, datetime

import pytest

from domain.models import Game, Player, Round, RoundStatus, Table, TournamentStatus
from tests.utils import ServiceBundle, build_db_url, build_services


def _bootstrap_single_game(prefix: str) -> tuple[ServiceBundle, int]:
    services = build_services(build_db_url(prefix))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    table_repo = services["table_repo"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=2,
        current_round=1,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    table_repo.add(Table(id=None, number=1, location="A"))
    p1 = player_repo.add(Player(id=None, telegram_id=8501, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=8502, username="u2", full_name="B", rating=1450))
    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game = game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )
    return services, game.id or 0


def test_matching_reports_require_manual_end_round_before_next_round() -> None:
    services, _ = _bootstrap_single_game("manual_end_reports")
    result_service = services["result_service"]
    pairing_service = services["pairing_service"]
    tournament_service = services["tournament_service"]
    round_repo = services["round_repo"]

    result_service.submit_player_report(8501, "draw")
    agreed = result_service.submit_player_report(8502, "draw")
    assert agreed.round_closed is True

    round_after_reports = round_repo.get_by_number(1)
    assert round_after_reports is not None
    assert round_after_reports.status == RoundStatus.ONGOING

    with pytest.raises(ValueError):
        pairing_service.prepare_round(1, 9001)

    tournament_service.end_current_round()
    closed_round = round_repo.get_by_number(1)
    assert closed_round is not None
    assert closed_round.status == RoundStatus.CLOSED

    prepared = pairing_service.prepare_round(1, 9001)
    assert prepared.round_number == 2


def test_approve_result_requires_manual_end_round_before_next_round() -> None:
    services, game_id = _bootstrap_single_game("manual_end_approve")
    result_service = services["result_service"]
    pairing_service = services["pairing_service"]
    tournament_service = services["tournament_service"]
    round_repo = services["round_repo"]

    approved = result_service.approve_result(game_id, "1-0")
    assert approved.round_closed is True

    round_after_approve = round_repo.get_by_number(1)
    assert round_after_approve is not None
    assert round_after_approve.status == RoundStatus.ONGOING

    with pytest.raises(ValueError):
        pairing_service.prepare_round(1, 9001)

    tournament_service.end_current_round()
    closed_round = round_repo.get_by_number(1)
    assert closed_round is not None
    assert closed_round.status == RoundStatus.CLOSED


def test_approve_result_allowed_for_closed_round_when_next_not_prepared() -> None:
    services, game_id = _bootstrap_single_game("approve_after_close")
    result_service = services["result_service"]
    tournament_service = services["tournament_service"]

    result_service.approve_result(game_id, "1-0")
    tournament_service.end_current_round()

    changed = result_service.approve_result(game_id, "0.5-0.5")
    assert changed.confirmed_result == "0.5-0.5"
    assert changed.reseed_required is False
