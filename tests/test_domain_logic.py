from bot.domain.enums import RoundStatus, TournamentStatus
from bot.domain.scoring import apply_result
from bot.domain.swiss import swiss_pairings
from bot.domain.tiebreaks import MatchRecord, calculate_buchholz, calculate_sonneborn_berger
from bot.domain.validators import InvariantViolationError, validate_can_finish_tournament, validate_can_generate_round


def test_swiss_pairings_avoids_rematch_and_respects_bye_rule() -> None:
    pairs = swiss_pairings(
        [1, 2, 3, 4, 5],
        scores={1: 2.0, 2: 2.0, 3: 1.0, 4: 1.0, 5: 0.0},
        history=[(1, 2)],
        had_bye={5},
    )

    assert (1, 2) not in pairs and (2, 1) not in pairs
    assert (4, None) in pairs


def test_swiss_pairings_avoids_three_same_colors() -> None:
    pairs = swiss_pairings(
        [1, 2],
        color_history={1: "WW", 2: "BB"},
    )
    assert pairs == [(2, 1)]


def test_apply_result_variants() -> None:
    assert apply_result("1-0").white == 1.0
    assert apply_result("0-1").black == 1.0
    assert apply_result("0.5-0.5").white == 0.5
    assert apply_result("bye").white == 1.0
    assert apply_result("forfeit").white == 1.0


def test_tiebreaks() -> None:
    points = {1: 2.0, 2: 1.0, 3: 0.0}
    matches = [
        MatchRecord(player_id=1, opponent_id=2, score=1.0),
        MatchRecord(player_id=1, opponent_id=3, score=1.0),
        MatchRecord(player_id=2, opponent_id=1, score=0.0),
    ]
    assert calculate_buchholz(points, matches)[1] == 1.0
    assert calculate_sonneborn_berger(points, matches)[1] == 1.0


def test_validators() -> None:
    try:
        validate_can_generate_round(current_round_status=RoundStatus.ACTIVE)
    except InvariantViolationError:
        pass
    else:
        raise AssertionError("expected invariant violation")

    try:
        validate_can_finish_tournament(
            tournament_status=TournamentStatus.ACTIVE,
            has_unfinished_rounds=True,
            has_pending_games=False,
        )
    except InvariantViolationError:
        pass
    else:
        raise AssertionError("expected invariant violation")
