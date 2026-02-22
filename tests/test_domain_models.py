import pytest

from domain.models import Player


def test_player_tiebreakers_are_computed() -> None:
    player = Player(id=1, tournament_id=1, telegram_user_id=11, display_name="A")

    player.update_tiebreakers(
        opponents_scores=[3.5, 4.0, 2.5, 5.0],
        game_results=[(1.0, 3.5), (0.5, 4.0), (1.0, 2.5), (0.0, 5.0)],
    )

    assert player.buchholz == 15.0
    assert player.median_buchholz == 7.5
    assert player.sonneborn_berger == 8.0


def test_player_tiebreakers_validate_inputs() -> None:
    player = Player(id=1, tournament_id=1, telegram_user_id=11, display_name="A")

    with pytest.raises(ValueError, match="equal lengths"):
        player.update_tiebreakers(opponents_scores=[1.0], game_results=[])

    with pytest.raises(ValueError, match="Result points"):
        player.update_tiebreakers(opponents_scores=[1.0], game_results=[(0.75, 1.0)])
