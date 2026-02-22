"""Swiss pairing and tie-break domain logic.

This module intentionally stays framework-agnostic so algorithms can be reused
from handlers, background jobs, or tests.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class Standing:
    """Current standing snapshot for a tournament participant."""

    player_id: int
    points: float
    buchholz: float
    sonneborn_berger: float


def sort_standings(standings: list[Standing]) -> list[Standing]:
    """Sort standings using points and classical Swiss tie-break priority."""
    return sorted(
        standings,
        key=lambda item: (item.points, item.buchholz, item.sonneborn_berger),
        reverse=True,
    )


def swiss_pairings(
    player_ids: list[int],
    *,
    scores: Mapping[int, float] | None = None,
    history: Iterable[tuple[int, int]] | None = None,
    color_history: Mapping[int, str] | None = None,
    had_bye: set[int] | None = None,
) -> list[tuple[int, int | None]]:
    """Build Swiss pairings with score-groups, no rematches and color constraints.

    Returned tuple order is ``(white_player_id, black_player_id | None)``.
    """
    if not player_ids:
        return []

    score_map = scores or {}
    color_map = color_history or {}
    bye_players = had_bye or set()
    played = _build_history_map(history or [])

    ordered = list(player_ids)
    bye_pair: tuple[int, int | None] | None = None
    if len(ordered) % 2 == 1:
        bye_idx = next((i for i in range(len(ordered) - 1, -1, -1) if ordered[i] not in bye_players), len(ordered) - 1)
        bye_player = ordered.pop(bye_idx)
        bye_pair = (bye_player, None)

    pairs = _find_pairings(ordered, played, color_map, score_map)
    if pairs is None:
        raise ValueError("Unable to create Swiss pairings without violating constraints")

    result_pairs: list[tuple[int, int | None]] = list(pairs)
    if bye_pair is not None:
        result_pairs.append(bye_pair)
    return result_pairs


def _build_history_map(history: Iterable[tuple[int, int]]) -> dict[int, set[int]]:
    played: dict[int, set[int]] = defaultdict(set)
    for p1, p2 in history:
        played[p1].add(p2)
        played[p2].add(p1)
    return played


def _find_pairings(
    players: list[int],
    played: Mapping[int, set[int]],
    color_map: Mapping[int, str],
    score_map: Mapping[int, float],
) -> list[tuple[int, int]] | None:
    if not players:
        return []

    first = players[0]
    first_played = played.get(first)
    candidate_indexes = sorted(
        range(1, len(players)),
        key=lambda idx: (abs(score_map.get(players[idx], 0.0) - score_map.get(first, 0.0)), idx),
    )

    for idx in candidate_indexes:
        second = players[idx]
        if first_played is not None and second in first_played:
            continue

        oriented = _choose_colors(first, second, color_map)
        if oriented is None:
            continue

        rest = players[1:idx] + players[idx + 1 :]
        suffix = _find_pairings(rest, played, color_map, score_map)
        if suffix is not None:
            return [oriented, *suffix]

    return None


def _choose_colors(p1: int, p2: int, color_map: Mapping[int, str]) -> tuple[int, int] | None:
    variants = [(p1, p2), (p2, p1)]
    candidates: list[tuple[int, int, int]] = []

    for white, black in variants:
        if _creates_three_in_row(color_map.get(white, ""), "W"):
            continue
        if _creates_three_in_row(color_map.get(black, ""), "B"):
            continue
        balance_cost = _color_balance_cost(color_map.get(white, ""), "W") + _color_balance_cost(
            color_map.get(black, ""),
            "B",
        )
        candidates.append((balance_cost, white, black))

    if not candidates:
        return None

    _, white, black = min(candidates, key=lambda item: item[0])
    return (white, black)


def _creates_three_in_row(history: str, color: str) -> bool:
    return len(history) >= 2 and history[-1] == color and history[-2] == color


def _color_balance_cost(history: str, assigned_color: str) -> int:
    whites = history.count("W") + (1 if assigned_color == "W" else 0)
    blacks = history.count("B") + (1 if assigned_color == "B" else 0)
    return abs(whites - blacks)
