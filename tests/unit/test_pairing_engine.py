import pytest

from services.pairing_engine import (
    InsufficientTablesError,
    PairingPlayer,
    TableSlot,
    generate_pairings,
)


def _player(
    player_id: int,
    score: float,
    rating: int = 0,
    opponents: set[int] | None = None,
    color_history: tuple[str, ...] = (),
    had_bye: bool = False,
) -> PairingPlayer:
    return PairingPlayer(
        player_id=player_id,
        display_name=f"P{player_id}",
        score=score,
        rating=rating,
        opponents=frozenset(opponents or set()),
        color_history=color_history,
        had_bye=had_bye,
    )


def test_pairing_engine_avoids_rematch_when_possible() -> None:
    players = [
        _player(1, 2.0, opponents={2}),
        _player(2, 2.0, opponents={1}),
        _player(3, 2.0),
        _player(4, 2.0),
    ]
    tables = [TableSlot(number=1, location="Main", place="A"), TableSlot(number=2, location="Main", place="B")]
    result = generate_pairings(players, tables)
    pairs = {tuple(sorted((game.white_player_id, game.black_player_id))) for game in result.games}
    assert (1, 2) not in pairs


def test_pairing_engine_requests_confirmation_if_repeat_unavoidable() -> None:
    players = [_player(1, 1.0, opponents={2}), _player(2, 1.0, opponents={1})]
    tables = [TableSlot(number=1, location="Main", place="A")]
    result = generate_pairings(players, tables)
    assert result.confirmation_request is not None
    assert result.confirmation_request.repeated_games == ((1, 2),)


def test_pairing_engine_handles_bye_policy() -> None:
    players = [_player(1, 2.0, had_bye=True), _player(2, 1.0), _player(3, 0.0, had_bye=True)]
    result = generate_pairings(players, [TableSlot(number=1, location="Main", place="A")])
    assert result.bye is not None
    assert result.bye.player_id == 2


def test_pairing_engine_checks_tables_count() -> None:
    with pytest.raises(InsufficientTablesError):
        generate_pairings(
            [_player(1, 1.0), _player(2, 1.0), _player(3, 1.0), _player(4, 1.0)],
            [TableSlot(number=1, location="Main", place="Only")],
        )


def test_pairing_engine_uses_rating_inside_same_score_group() -> None:
    players = [
        _player(1, 1.0, rating=2200),
        _player(2, 1.0, rating=2100),
        _player(3, 1.0, rating=1200),
        _player(4, 1.0, rating=1100),
    ]
    tables = [TableSlot(number=1, location="Main", place="A"), TableSlot(number=2, location="Main", place="B")]
    result = generate_pairings(players, tables)
    top_pair = tuple(sorted((result.games[0].white_player_id, result.games[0].black_player_id)))
    assert top_pair == (1, 2)
