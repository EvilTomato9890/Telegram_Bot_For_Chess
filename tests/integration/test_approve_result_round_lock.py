from datetime import UTC, datetime

import pytest

from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
from tests.utils import build_db_url, build_services


def test_approve_result_allowed_only_for_current_round() -> None:
    services = build_services(build_db_url("approve_lock"))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    result_service = services["result_service"]

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

    p1 = player_repo.add(Player(id=None, telegram_id=7001, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=7002, username="u2", full_name="B", rating=1450))
    round1 = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game1 = game_repo.add(
        Game(
            id=None,
            round_id=round1.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )

    result_service.approve_result(game1.id or 0, "1-0")

    round_repo.add(Round(id=None, number=2, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=2,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )

    with pytest.raises(ValueError, match="только в текущем туре"):
        result_service.approve_result(game1.id or 0, "0-1")

