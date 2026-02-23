"""Swiss-style pairing engine with repeat and color constraints."""

from __future__ import annotations

from dataclasses import dataclass


class PairingEngineError(ValueError):
    """Base controlled error for pairing generation failures."""


class InsufficientTablesError(PairingEngineError):
    """Raised when there are fewer tables than required games in a round."""


@dataclass(frozen=True, slots=True)
class PairingPlayer:
    """Minimal player data required by the pairing engine."""

    player_id: int
    display_name: str
    score: float
    rating: int
    opponents: frozenset[int]
    color_history: tuple[str, ...]
    had_bye: bool = False


@dataclass(frozen=True, slots=True)
class TableSlot:
    """Playable table metadata."""

    number: int
    location: str
    place: str


@dataclass(frozen=True, slots=True)
class GamePairing:
    """Pairing result assigned to one board."""

    table_number: int
    location: str
    place: str
    white_player_id: int
    black_player_id: int


@dataclass(frozen=True, slots=True)
class ByeAssignment:
    """Assigned bye player for odd-size round."""

    player_id: int
    repeated: bool


@dataclass(frozen=True, slots=True)
class PairingConfirmationRequest:
    """Organizer confirmation payload when strict constraints are impossible."""

    reason: str
    repeated_games: tuple[tuple[int, int], ...]
    repeated_bye_player_id: int | None


@dataclass(frozen=True, slots=True)
class PairingResult:
    """Complete pairing engine output."""

    games: tuple[GamePairing, ...]
    bye: ByeAssignment | None
    notifications: tuple[str, ...]
    confirmation_request: PairingConfirmationRequest | None


@dataclass(frozen=True, slots=True)
class _PairingPlan:
    pairs: list[tuple[PairingPlayer, PairingPlayer]]
    bye: ByeAssignment | None
    confirmation_request: PairingConfirmationRequest | None


def generate_pairings(players: list[PairingPlayer], tables: list[TableSlot]) -> PairingResult:
    """Generate pairings by score groups with repeat/bye/color constraints."""

    games_in_round = len(players) // 2
    if len(tables) < games_in_round:
        raise InsufficientTablesError(
            f"insufficient tables: required {games_in_round}, provided {len(tables)}"
        )

    ordered_players = sorted(players, key=lambda player: (-player.score, -player.rating, player.player_id))
    pairing_plan = _select_pairing_plan(ordered_players)
    games = tuple(
        GamePairing(
            table_number=slot.number,
            location=slot.location,
            place=slot.place,
            white_player_id=white.player_id,
            black_player_id=black.player_id,
        )
        for slot, (white, black) in zip(tables, pairing_plan.pairs)
    )
    notifications = tuple(
        f"Board {game.table_number}: {game.white_player_id} (White) vs "
        f"{game.black_player_id} (Black) - {game.location}, {game.place}."
        for game in games
    )
    if pairing_plan.bye is not None:
        notifications = (*notifications, f"Player {pairing_plan.bye.player_id} receives a bye.")
    return PairingResult(
        games=games,
        bye=pairing_plan.bye,
        notifications=notifications,
        confirmation_request=pairing_plan.confirmation_request,
    )


def _select_pairing_plan(players: list[PairingPlayer]) -> _PairingPlan:
    bye_options = _bye_options(players)
    for bye, remaining_players, bye_confirmation in bye_options:
        strict_pairs = _build_pairs(remaining_players, allow_repeats=False)
        if strict_pairs is not None:
            return _PairingPlan(pairs=strict_pairs, bye=bye, confirmation_request=bye_confirmation)

    for bye, remaining_players, bye_confirmation in bye_options:
        relaxed_pairs = _build_pairs(remaining_players, allow_repeats=True)
        if relaxed_pairs is None:
            continue
        repeated_games = tuple(
            (
                min(white.player_id, black.player_id),
                max(white.player_id, black.player_id),
            )
            for white, black in relaxed_pairs
            if black.player_id in white.opponents
        )
        return _PairingPlan(
            pairs=relaxed_pairs,
            bye=bye,
            confirmation_request=(
                PairingConfirmationRequest(
                    reason="Unable to avoid repeated opponents with current score groups.",
                    repeated_games=repeated_games,
                    repeated_bye_player_id=bye.player_id if bye and bye.repeated else None,
                )
                if repeated_games
                else bye_confirmation
            ),
        )
    raise PairingEngineError("unable to generate pairings for this round")


def _bye_options(
    players: list[PairingPlayer],
) -> list[tuple[ByeAssignment | None, list[PairingPlayer], PairingConfirmationRequest | None]]:
    if len(players) % 2 == 0:
        return [(None, players, None)]
    sorted_for_bye = sorted(players, key=lambda player: (player.score, player.player_id))
    preferred = [player for player in sorted_for_bye if not player.had_bye]
    repeated = [player for player in sorted_for_bye if player.had_bye]
    options: list[tuple[ByeAssignment | None, list[PairingPlayer], PairingConfirmationRequest | None]] = []
    for player in [*preferred, *repeated]:
        bye = ByeAssignment(player_id=player.player_id, repeated=player.had_bye)
        confirmation = (
            PairingConfirmationRequest(
                reason="All players already had a bye; assigning repeated bye requires confirmation.",
                repeated_games=tuple(),
                repeated_bye_player_id=player.player_id,
            )
            if player.had_bye
            else None
        )
        options.append(
            (
                bye,
                [candidate for candidate in players if candidate.player_id != player.player_id],
                confirmation,
            )
        )
    return options


def _build_pairs(players: list[PairingPlayer], *, allow_repeats: bool) -> list[tuple[PairingPlayer, PairingPlayer]] | None:
    if not players:
        return []
    first = players[0]
    candidates = players[1:]
    scored_candidates: list[tuple[int, tuple[PairingPlayer, PairingPlayer], list[PairingPlayer]]] = []
    for candidate in candidates:
        if not allow_repeats and candidate.player_id in first.opponents:
            continue
        white, black = _choose_colors(first, candidate)
        penalty = _pair_penalty(white, black)
        remaining = [player for player in players if player.player_id not in {first.player_id, candidate.player_id}]
        scored_candidates.append((penalty, (white, black), remaining))
    for _, pair, remaining_players in sorted(scored_candidates, key=lambda item: item[0]):
        tail_pairs = _build_pairs(remaining_players, allow_repeats=allow_repeats)
        if tail_pairs is not None:
            return [pair, *tail_pairs]
    return None


def _choose_colors(left: PairingPlayer, right: PairingPlayer) -> tuple[PairingPlayer, PairingPlayer]:
    left_white = _color_penalty_with(left, "W") + _color_penalty_with(right, "B")
    right_white = _color_penalty_with(left, "B") + _color_penalty_with(right, "W")
    if left_white <= right_white:
        return left, right
    return right, left


def _pair_penalty(white: PairingPlayer, black: PairingPlayer) -> int:
    return _color_penalty_with(white, "W") + _color_penalty_with(black, "B")


def _color_penalty_with(player: PairingPlayer, new_color: str) -> int:
    recent = player.color_history[-2:]
    if len(recent) < 2:
        return 0
    if recent[0] == recent[1] == new_color:
        return 100
    return 0
