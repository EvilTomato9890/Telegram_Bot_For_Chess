from domain.models import Table, TournamentStatus
from tests.utils import build_db_url, build_services


def test_full_tournament_flow_registration_to_finish() -> None:
    services = build_services(build_db_url("e2e"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    pairing_service = services["pairing_service"]
    result_service = services["result_service"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]

    tournament_service.create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    services["table_repo"].add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    registration_service.register(11, "u1", "A", 1500)
    registration_service.register(22, "u2", "B", 1400)
    registration_service.register(33, "u3", "C", 1300)
    registration_service.register(44, "u4", "D", 1200)
    tournament_service.set_round_number(2, confirm=True)
    tournament_service.prepare_tournament()
    tournament = tournament_service.start_tournament()
    assert tournament.status == TournamentStatus.ONGOING

    round1 = pairing_service.generate_next_round(1, 9001)
    assert round1.round_number == 1
    for game in round1.games:
        if game.is_bye:
            continue
        result_service.approve_result(game.id or 0, "1-0")
    tournament_service.end_current_round()

    round2 = pairing_service.generate_next_round(1, 9001)
    for game in round2.games:
        if game.is_bye:
            continue
        result_service.approve_result(game.id or 0, "0.5-0.5")
    tournament_service.end_current_round()

    finished = tournament_service.finish_tournament()
    assert finished.status == TournamentStatus.FINISHED
