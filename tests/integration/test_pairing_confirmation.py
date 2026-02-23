from datetime import UTC, datetime

from domain.models import Game, GameResult, Player, Round, RoundStatus, Table, TournamentStatus
from tests.utils import build_db_url, build_services


def test_confirm_next_round_uses_stored_payload_without_recalculation() -> None:
    services = build_services(build_db_url("pairing_confirm"))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    table_repo = services["table_repo"]
    pairing_service = services["pairing_service"]

    # Bootstrap ongoing tournament with one closed round where players met already.
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
    p1 = player_repo.add(Player(id=None, telegram_id=101, username="u1", full_name="A", rating=1500, score=1.0))
    p2 = player_repo.add(Player(id=None, telegram_id=102, username="u2", full_name="B", rating=1400, score=1.0))
    table_repo.add(Table(id=None, number=1, location="Main", place_hint=None))
    round_1 = round_repo.add(Round(id=None, number=1, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))
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

    # Request next round and require confirmation (unavoidable rematch).
    outcome = pairing_service.generate_next_round(1, 9001, force=False)
    assert outcome.needs_confirmation is True

    # Remove all tables; direct recomputation would now fail by insufficient tables.
    for table in table_repo.list_all():
        table_repo.remove_by_number(table.number)

    confirmed = pairing_service.confirm_next_round(1, 9001)
    assert confirmed.needs_confirmation is False
    assert confirmed.round_number == 2
    assert len(confirmed.games) == 1
