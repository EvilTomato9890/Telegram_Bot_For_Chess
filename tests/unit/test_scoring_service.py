from datetime import UTC, datetime

from domain.models import Game, GameResult, Player, Round, RoundStatus
from tests.utils import build_db_url, build_services


def test_scoring_service_recalculates_tie_breaks() -> None:
    services = build_services(build_db_url("scoring"))
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    scoring = services["scoring_service"]

    p1 = player_repo.add(Player(id=None, telegram_id=101, username="a", full_name="Alpha", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=102, username="b", full_name="Beta", rating=1400))
    p3 = player_repo.add(Player(id=None, telegram_id=103, username="c", full_name="Gamma", rating=1300))
    round_1 = round_repo.add(Round(id=None, number=1, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))
    round_2 = round_repo.add(Round(id=None, number=2, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))

    game_repo.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
            result=GameResult.WHITE_WIN,
        )
    )
    game_repo.add(
        Game(
            id=None,
            round_id=round_2.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p3.id or 0,
            result=GameResult.DRAW,
        )
    )

    standings = scoring.recalculate()
    assert standings[0].full_name == "Alpha"
    assert standings[0].score == 1.5
    assert standings[1].score >= standings[2].score

