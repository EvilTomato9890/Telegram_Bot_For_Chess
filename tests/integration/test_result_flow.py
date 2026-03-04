from datetime import UTC, datetime

from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
from services import NotificationService, ResultService
from tests.utils import ServiceBundle, build_db_url, build_services


def _bootstrap_game() -> tuple[ServiceBundle, int, ResultService, NotificationService]:
    services = build_services(build_db_url("result_flow"))
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    tournament_repo = services["tournament_repo"]
    result_service = services["result_service"]
    notification_service = services["notification_service"]

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

    p1 = player_repo.add(Player(id=None, telegram_id=501, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=502, username="u2", full_name="B", rating=1400))
    round_ = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game = game_repo.add(
        Game(
            id=None,
            round_id=round_.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )
    return services, game.id or 0, result_service, notification_service


def test_conflicting_reports_require_resolution() -> None:
    _services, _game_id, result_service, notification_service = _bootstrap_game()
    out1 = result_service.submit_player_report(501, "white")
    out2 = result_service.submit_player_report(502, "black")
    assert out1.status == "pending"
    assert out2.status == "conflict"
    assert "1-0" in out2.message
    assert "0-1" in out2.message
    # No global broadcast notifications on conflict.
    assert notification_service.flush() == []


def test_matching_reports_finalize_game() -> None:
    services, game_id, result_service, _notification_service = _bootstrap_game()
    out1 = result_service.submit_player_report(501, "draw")
    out2 = result_service.submit_player_report(502, "draw")
    assert out1.status == "pending"
    assert out2.status == "agreed"
    assert out2.confirmed_result == "0.5-0.5"
    game = services["game_repo"].get_by_id(game_id)
    assert game is not None
    assert game.result is not None
