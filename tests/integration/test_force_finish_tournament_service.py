from datetime import UTC, datetime

import pytest

from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
from tests.utils import build_db_url, build_services


def test_force_finish_tournament_bypasses_validate_finish_preconditions() -> None:
    services = build_services(build_db_url("force_finish_service"))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    tournament_service = services["tournament_service"]

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
    p1 = player_repo.add(Player(id=None, telegram_id=9101, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=9102, username="u2", full_name="B", rating=1400))
    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )

    with pytest.raises(ValueError):
        tournament_service.validate_finish_tournament()

    forced = tournament_service.force_finish_tournament()
    assert forced.status == TournamentStatus.FINISHED
