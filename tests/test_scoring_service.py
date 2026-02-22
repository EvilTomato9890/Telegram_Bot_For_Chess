from domain.models import Game, Player, Round
from repositories import GameRepository, PlayerRepository, RoundRepository
from services import ScoringService


def test_scoring_service_builds_standings_and_player_stats() -> None:
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    game_repository = GameRepository()
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )

    p1 = player_repository.add(Player(id=None, tournament_id=7, telegram_user_id=101, display_name="Alice"))
    p2 = player_repository.add(Player(id=None, tournament_id=7, telegram_user_id=102, display_name="Bob"))
    p3 = player_repository.add(Player(id=None, tournament_id=7, telegram_user_id=103, display_name="Carol"))

    round_1 = round_repository.add(Round(id=None, tournament_id=7, number=1))
    game_1 = game_repository.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            table_id=None,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )
    game_2 = game_repository.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            table_id=None,
            white_player_id=p3.id or 0,
            black_player_id=p3.id or 0,
        )
    )

    scoring_service.submit_result(game_1.id or 0, "1-0")
    scoring_service.submit_result(game_2.id or 0, "bye")

    standings = scoring_service.build_standings(tournament_id=7)

    assert [entry.display_name for entry in standings] == ["Alice", "Carol", "Bob"]
    assert standings[0].score == 1.0
    assert standings[0].buchholz == 0.0
    assert standings[0].position == 1
    assert standings[1].score == 1.0
    assert standings[1].buchholz == 0.0
    assert standings[1].position == 2
    assert standings[2].score == 0.0
    assert standings[2].position == 3

    my_score = scoring_service.get_my_score(tournament_id=7, telegram_user_id=103)
    assert my_score.display_name == "Carol"
    assert my_score.position == 2

    top_view = scoring_service.get_standings(tournament_id=7, top_n=2, telegram_user_id=102)
    assert len(top_view.top) == 2
    assert top_view.player_position == 3


def test_scoring_service_validates_inputs() -> None:
    scoring_service = ScoringService(
        player_repository=PlayerRepository(),
        round_repository=RoundRepository(),
        game_repository=GameRepository(),
    )

    try:
        scoring_service.get_standings(tournament_id=1, top_n=0)
    except ValueError as error:
        assert "top_n must be positive" in str(error)
    else:
        raise AssertionError("expected ValueError")



def test_scoring_service_validates_bye_game_shape() -> None:
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    game_repository = GameRepository()
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )

    p1 = player_repository.add(Player(id=None, tournament_id=3, telegram_user_id=301, display_name="One"))
    p2 = player_repository.add(Player(id=None, tournament_id=3, telegram_user_id=302, display_name="Two"))
    round_1 = round_repository.add(Round(id=None, tournament_id=3, number=1))

    normal_game = game_repository.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            table_id=None,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )
    bye_game = game_repository.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            table_id=None,
            white_player_id=p1.id or 0,
            black_player_id=p1.id or 0,
        )
    )

    try:
        scoring_service.submit_result(normal_game.id or 0, "bye")
    except ValueError as error:
        assert "bye result requires" in str(error)
    else:
        raise AssertionError("expected ValueError")

    try:
        scoring_service.submit_result(bye_game.id or 0, "1-0")
    except ValueError as error:
        assert "self-pairing" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_build_standings_ignores_games_with_foreign_players() -> None:
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    game_repository = GameRepository()
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )

    p1 = player_repository.add(Player(id=None, tournament_id=11, telegram_user_id=401, display_name="A"))
    player_repository.add(Player(id=None, tournament_id=11, telegram_user_id=402, display_name="B"))
    round_1 = round_repository.add(Round(id=None, tournament_id=11, number=1))

    game = game_repository.add(
        Game(
            id=None,
            round_id=round_1.id or 0,
            table_id=None,
            white_player_id=p1.id or 0,
            black_player_id=9999,
        )
    )
    scoring_service.submit_result(game.id or 0, "1-0")

    standings = scoring_service.build_standings(tournament_id=11)

    assert standings[0].display_name == "A"
    assert standings[0].score == 0.0
    assert standings[1].display_name == "B"
    assert standings[1].score == 0.0
