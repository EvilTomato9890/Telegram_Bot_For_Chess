from datetime import UTC, datetime

import pytest

from domain.exceptions import OrganizerConfirmationRequiredError
from domain.models import Game, GameResult, Player, Round, RoundStatus, Table, TournamentStatus
from tests.utils import ServiceBundle, build_db_url, build_services


def _bootstrap_closed_round_with_results(prefix: str, *, prepare_next_round: bool) -> tuple[ServiceBundle, int]:
    services = build_services(build_db_url(prefix))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    table_repo = services["table_repo"]
    pairing_service = services["pairing_service"]
    scoring_service = services["scoring_service"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=1,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))

    p1 = player_repo.add(Player(id=None, telegram_id=8701, username="u1", full_name="A", rating=1600))
    p2 = player_repo.add(Player(id=None, telegram_id=8702, username="u2", full_name="B", rating=1500))
    p3 = player_repo.add(Player(id=None, telegram_id=8703, username="u3", full_name="C", rating=1400))
    p4 = player_repo.add(Player(id=None, telegram_id=8704, username="u4", full_name="D", rating=1300))

    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))
    game_to_change = game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
            result=GameResult.WHITE_WIN,
            result_source="arbiter",
        )
    )
    game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=2,
            white_player_id=p3.id or 0,
            black_player_id=p4.id or 0,
            result=GameResult.BLACK_WIN,
            result_source="arbiter",
        )
    )
    scoring_service.recalculate()

    if prepare_next_round:
        pairing_service.prepare_round(1, 9001)

    return services, game_to_change.id or 0


def test_closed_round_change_allowed_when_next_round_not_prepared() -> None:
    services, game_id = _bootstrap_closed_round_with_results("retro_no_pending", prepare_next_round=False)
    result_service = services["result_service"]

    changed = result_service.approve_result(game_id, "0.5-0.5")
    assert changed.confirmed_result == "0.5-0.5"
    assert changed.reseed_required is False


def test_closed_round_change_requires_organizer_confirmation_when_next_round_prepared() -> None:
    services, game_id = _bootstrap_closed_round_with_results("retro_need_confirm", prepare_next_round=True)
    result_service = services["result_service"]

    with pytest.raises(OrganizerConfirmationRequiredError):
        result_service.approve_result(game_id, "0.5-0.5")


def test_closed_round_change_with_confirmation_marks_reseed_required() -> None:
    services, game_id = _bootstrap_closed_round_with_results("retro_confirmed", prepare_next_round=True)
    result_service = services["result_service"]

    changed = result_service.approve_result(game_id, "0.5-0.5", allow_prepared_override=True)
    assert changed.confirmed_result == "0.5-0.5"
    assert changed.reseed_required is True
