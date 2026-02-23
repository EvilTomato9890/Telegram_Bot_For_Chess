import pytest

from domain.models import Game, Player, Round
from repositories import GameRepository, PlayerRepository, RoundRepository
from services import AccessControlService, NotificationService, ResultReportingService, ScoringService


def _build_service() -> tuple[ResultReportingService, GameRepository, NotificationService]:
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    game_repository = GameRepository()
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )
    notification_service = NotificationService()
    access_control_service = AccessControlService.from_config(admin_ids=[1], arbitrs_ids=[2])

    player_repository.add(Player(id=10, tournament_id=77, telegram_user_id=1001, display_name="A"))
    player_repository.add(Player(id=20, tournament_id=77, telegram_user_id=1002, display_name="B"))
    player_repository.add(Player(id=30, tournament_id=77, telegram_user_id=1003, display_name="C"))
    r1 = round_repository.add(Round(id=None, tournament_id=77, number=1))
    r2 = round_repository.add(Round(id=None, tournament_id=77, number=2))

    game_repository.add(
        Game(
            id=None,
            round_id=r1.id or 0,
            table_id=None,
            white_player_id=10,
            black_player_id=30,
            result="1-0",
        )
    )
    game_repository.add(
        Game(
            id=None,
            round_id=r2.id or 0,
            table_id=None,
            white_player_id=10,
            black_player_id=20,
        )
    )

    service = ResultReportingService(
        game_repository=game_repository,
        round_repository=round_repository,
        scoring_service=scoring_service,
        notification_service=notification_service,
        access_control_service=access_control_service,
    )
    return service, game_repository, notification_service


def test_report_is_stored_by_current_game_and_resolved_on_match() -> None:
    service, game_repository, notification_service = _build_service()

    resolution_1 = service.submit_report(player_id=10, result="1-0")
    resolution_2 = service.submit_report(player_id=20, result="1-0")

    game = game_repository.get(resolution_1.game_id)
    assert resolution_1.status == "pending"
    assert resolution_2.status == "agreed"
    assert game is not None
    assert game.result == "1-0"
    assert any("agreed" in message for message in notification_service.flush())


def test_report_conflict_notifies_players_and_allows_overwrite() -> None:
    service, game_repository, notification_service = _build_service()

    game_id = service.submit_report(player_id=10, result="1-0").game_id
    conflict = service.submit_report(player_id=20, result="0-1")
    assert conflict.status == "conflict"

    messages = notification_service.flush()
    assert any("reported different results" in message for message in messages)

    agreed = service.submit_report(player_id=20, result="1-0")
    game = game_repository.get(game_id)
    assert agreed.status == "agreed"
    assert game is not None
    assert game.result == "1-0"


def test_latest_report_from_same_player_overwrites_previous_pending_report() -> None:
    service, game_repository, _ = _build_service()

    game_id = service.submit_report(player_id=10, result="1-0").game_id
    rewritten = service.submit_report(player_id=10, result="0-1")
    resolved = service.submit_report(player_id=20, result="0-1")

    game = game_repository.get(game_id)
    assert rewritten.status == "pending"
    assert resolved.status == "agreed"
    assert game is not None
    assert game.result == "0-1"


def test_player_cannot_re_report_after_result_finalized() -> None:
    service, _, _ = _build_service()

    service.submit_report(player_id=10, result="1-0")
    service.submit_report(player_id=20, result="1-0")

    with pytest.raises(ValueError, match="already finalized"):
        service.submit_report(player_id=10, result="0-1")

def test_player_can_report_only_own_current_or_last_game() -> None:
    service, _, _ = _build_service()

    with pytest.raises(ValueError, match="player has no games"):
        service.submit_report(player_id=999, result="1-0")


def test_arbiter_can_force_approve_result() -> None:
    service, game_repository, notification_service = _build_service()
    game_id = service.submit_report(player_id=10, result="1-0").game_id

    updated = service.approve_result(arbiter_user_id=2, game_id=game_id, result="0.5-0.5")

    assert updated.result == "0.5-0.5"
    stored = game_repository.get(game_id)
    assert stored is not None
    assert stored.result == "0.5-0.5"
    assert any("approved result" in message for message in notification_service.flush())


def test_non_arbiter_cannot_force_approve_result() -> None:
    service, _, _ = _build_service()
    game_id = service.submit_report(player_id=10, result="1-0").game_id

    with pytest.raises(ValueError, match="only arbiter/admin"):
        service.approve_result(arbiter_user_id=99, game_id=game_id, result="1-0")


def test_notifies_organizers_when_last_game_of_round_is_closed() -> None:
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    game_repository = GameRepository()
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )
    notification_service = NotificationService()
    access_control_service = AccessControlService.from_config(admin_ids=[1], arbitrs_ids=[2])

    player_repository.add(Player(id=10, tournament_id=77, telegram_user_id=1001, display_name="A"))
    player_repository.add(Player(id=20, tournament_id=77, telegram_user_id=1002, display_name="B"))
    player_repository.add(Player(id=30, tournament_id=77, telegram_user_id=1003, display_name="C"))
    player_repository.add(Player(id=40, tournament_id=77, telegram_user_id=1004, display_name="D"))

    round_ = round_repository.add(Round(id=None, tournament_id=77, number=2))
    game_repository.add(Game(id=None, round_id=round_.id or 0, table_id=None, white_player_id=10, black_player_id=20))
    game_repository.add(Game(id=None, round_id=round_.id or 0, table_id=None, white_player_id=30, black_player_id=40))

    service = ResultReportingService(
        game_repository=game_repository,
        round_repository=round_repository,
        scoring_service=scoring_service,
        notification_service=notification_service,
        access_control_service=access_control_service,
    )

    first_game_id = service.submit_report(player_id=10, result="1-0").game_id
    service.submit_report(player_id=20, result="1-0")
    assert game_repository.get(first_game_id) is not None

    service.submit_report(player_id=30, result="0-1")
    service.submit_report(player_id=40, result="0-1")

    messages = notification_service.flush()
    assert any("[ORGANIZERS]" in message for message in messages)
