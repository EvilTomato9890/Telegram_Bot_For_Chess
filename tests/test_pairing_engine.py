import pytest

from services.pairing_engine import (
    InsufficientTablesError,
    PairingPlayer,
    PairingConfirmationRequest,
    TableSlot,
    generate_pairings,
)


def _player(
    player_id: int,
    score: float,
    opponents: set[int] | None = None,
    color_history: tuple[str, ...] = (),
    had_bye: bool = False,
) -> PairingPlayer:
    return PairingPlayer(
        player_id=player_id,
        display_name=f"P{player_id}",
        score=score,
        opponents=frozenset(opponents or set()),
        color_history=color_history,
        had_bye=had_bye,
    )


def test_pairing_engine_uses_score_groups_and_assigns_tables() -> None:
    players = [
        _player(1, 2.0),
        _player(2, 2.0),
        _player(3, 1.0),
        _player(4, 1.0),
    ]
    tables = [TableSlot(location="Hall A", place="Near stage") for _ in range(2)]

    result = generate_pairings(players, tables)

    assert len(result.games) == 2
    assert result.games[0].table_number == 1
    assert result.games[1].table_number == 2
    assert result.games[0].location == "Hall A"
    assert "Hall A, Near stage" in result.notifications[0]
    assert result.confirmation_request is None


def test_pairing_engine_avoids_repeat_games_if_possible() -> None:
    players = [
        _player(1, 2.0, opponents={2}),
        _player(2, 2.0, opponents={1}),
        _player(3, 2.0),
        _player(4, 2.0),
    ]
    tables = [TableSlot(location="Main", place="A") for _ in range(2)]

    result = generate_pairings(players, tables)

    paired = {
        tuple(sorted((game.white_player_id, game.black_player_id)))
        for game in result.games
    }
    assert (1, 2) not in paired
    assert result.confirmation_request is None


def test_pairing_engine_requests_confirmation_when_repeat_is_unavoidable() -> None:
    players = [
        _player(1, 3.0, opponents={2}),
        _player(2, 3.0, opponents={1}),
    ]

    result = generate_pairings(players, [TableSlot(location="Main", place="B")])

    assert isinstance(result.confirmation_request, PairingConfirmationRequest)
    assert result.confirmation_request.repeated_games == ((1, 2),)


def test_pairing_engine_prevents_third_same_color_when_possible() -> None:
    players = [
        _player(1, 2.0, color_history=("W", "W")),
        _player(2, 2.0, color_history=("W", "W")),
        _player(3, 2.0, color_history=("B", "B")),
        _player(4, 2.0, color_history=("B", "B")),
    ]

    result = generate_pairings(players, [TableSlot(location="Main", place="A") for _ in range(2)])

    by_id = {}
    for game in result.games:
        by_id[game.white_player_id] = "W"
        by_id[game.black_player_id] = "B"

    assert by_id[1] == "B"
    assert by_id[2] == "B"
    assert by_id[3] == "W"
    assert by_id[4] == "W"


def test_pairing_engine_assigns_non_repeated_bye_if_possible() -> None:
    players = [
        _player(1, 2.0, had_bye=True),
        _player(2, 1.0, had_bye=False),
        _player(3, 1.0, had_bye=True),
    ]

    result = generate_pairings(players, [TableSlot(location="Main", place="A")])

    assert result.bye is not None
    assert result.bye.player_id == 2
    assert result.confirmation_request is None


def test_pairing_engine_tries_multiple_bye_candidates_before_allowing_repeats() -> None:
    players = [
        _player(1, 3.0, opponents={2, 3, 4}, had_bye=True),
        _player(2, 2.0, opponents={1}),
        _player(3, 2.0, opponents={1}),
        _player(4, 2.0, opponents={1}),
        _player(5, 0.0),
    ]

    result = generate_pairings(players, [TableSlot(location="Main", place="A") for _ in range(2)])

    assert result.bye is not None
    assert result.bye.player_id == 2
    assert result.confirmation_request is None


def test_pairing_engine_fails_when_tables_are_insufficient() -> None:
    with pytest.raises(InsufficientTablesError, match="insufficient tables"):
        generate_pairings(
            [_player(1, 1.0), _player(2, 1.0), _player(3, 1.0), _player(4, 1.0)],
            [TableSlot(location="Main", place="Only")],
        )
