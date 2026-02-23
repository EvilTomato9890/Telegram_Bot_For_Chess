from datetime import UTC, datetime

from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
from tests.utils import ServiceBundle, build_db_url, build_services


def _bootstrap_for_reports(prefix: str) -> tuple[ServiceBundle, int]:
    services = build_services(build_db_url(prefix))
    tournament_repo = services["tournament_repo"]
    round_repo = services["round_repo"]
    player_repo = services["player_repo"]
    game_repo = services["game_repo"]

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
    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    p1 = player_repo.add(Player(id=None, telegram_id=601, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=602, username="u2", full_name="B", rating=1450))
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


def test_pending_and_agreed_messages_include_result() -> None:
    services, game_id = _bootstrap_for_reports("result_msg_ok")
    result_service = services["result_service"]

    pending = result_service.submit_player_report(601, "white")
    agreed = result_service.submit_player_report(602, "white")

    assert "1-0" in pending.message
    assert "1-0" in agreed.message
    assert pending.game_id == game_id
    assert agreed.game_id == game_id


def test_conflict_message_contains_both_values() -> None:
    services, _ = _bootstrap_for_reports("result_msg_conflict")
    result_service = services["result_service"]

    result_service.submit_player_report(601, "white")
    conflict = result_service.submit_player_report(602, "black")

    assert "1-0" in conflict.message
    assert "0-1" in conflict.message
