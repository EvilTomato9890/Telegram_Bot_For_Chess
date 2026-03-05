import pytest

from domain.models import Player, Table, TournamentStatus
from tests.utils import build_db_url, build_services


def test_prepare_round_rebuilds_pairings_on_every_call() -> None:
    services = build_services(build_db_url("prepare_round_regen"))
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    table_repo = services["table_repo"]
    pairing_service = services["pairing_service"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=0,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))

    p1 = player_repo.add(Player(id=None, telegram_id=10101, username="u1", full_name="P1", rating=1800))
    player_repo.add(Player(id=None, telegram_id=10102, username="u2", full_name="P2", rating=1700))
    player_repo.add(Player(id=None, telegram_id=10103, username="u3", full_name="P3", rating=1600))
    p4 = player_repo.add(Player(id=None, telegram_id=10104, username="u4", full_name="P4", rating=1500))

    first = pairing_service.prepare_round(1, 9001)
    first_pairs = {(game.white_player_id, game.black_player_id) for game in first.games}

    boosted = player_repo.get_by_id(p4.id or 0)
    assert boosted is not None
    boosted.score = 5.0
    player_repo.update(boosted)

    second = pairing_service.prepare_round(1, 9001)
    second_pairs = {(game.white_player_id, game.black_player_id) for game in second.games}

    assert first_pairs != second_pairs
    assert p1.id is not None
    assert p4.id is not None
    assert (p1.id, p4.id) in second_pairs or (p4.id, p1.id) in second_pairs


def test_disqualify_invalidates_prepared_round_and_requires_reprepare() -> None:
    services = build_services(build_db_url("dq_invalidates_pending_round"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    pairing_service = services["pairing_service"]
    result_service = services["result_service"]
    game_repo = services["game_repo"]
    table_repo = services["table_repo"]
    tournament_repo = services["tournament_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    registration_service.register(11101, "u1", "A", 1700)
    registration_service.register(11102, "u2", "B", 1600)
    registration_service.register(11103, "u3", "C", 1500)
    registration_service.register(11104, "u4", "D", 1400)

    tournament_service.prepare_tournament()
    pairing_service.prepare_next_round_preview(1, 9001)
    pairing_service.generate_next_round(1, 9001, allow_prestart=True)
    tournament_service.start_tournament()

    for game in game_repo.list_all():
        if game.is_bye:
            continue
        result_service.approve_result(game.id or 0, "1-0")
    tournament_service.end_current_round()

    prepared = pairing_service.prepare_round(1, 9001)
    victim_id = prepared.games[0].white_player_id
    registration_service.disqualify(victim_id)

    updated_tournament = tournament_repo.get()
    assert updated_tournament is not None
    assert updated_tournament.pending_pairing_payload is None

    with pytest.raises(ValueError, match="Сначала выполните /prepare_round"):
        pairing_service.generate_next_round(1, 9001)

    pairing_service.prepare_round(1, 9001)
    started = pairing_service.generate_next_round(1, 9001)
    started_players = {
        player_id
        for game in started.games
        if not game.is_bye
        for player_id in (game.white_player_id, game.black_player_id)
    }
    assert victim_id not in started_players
