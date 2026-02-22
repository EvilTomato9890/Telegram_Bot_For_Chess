"""Tie-break calculations for Swiss tournaments.

Ranking order is fixed as:
1. Points
2. Buchholz (sum of opponents points)
3. Sonneborn-Berger
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class MatchRecord:
    """Single player's game against one opponent."""

    player_id: int
    opponent_id: int | None
    score: float


def calculate_points(results: Mapping[int, Iterable[float]]) -> dict[int, float]:
    """Return total points per player from list of per-round scores."""
    return {player_id: float(sum(values)) for player_id, values in results.items()}


def calculate_buchholz(points: Mapping[int, float], matches: Iterable[MatchRecord]) -> dict[int, float]:
    """Compute Buchholz: sum of opponents' final points."""
    totals: dict[int, float] = defaultdict(float)
    for match in matches:
        if match.opponent_id is None:
            continue
        totals[match.player_id] += points.get(match.opponent_id, 0.0)
    return dict(totals)


def calculate_sonneborn_berger(points: Mapping[int, float], matches: Iterable[MatchRecord]) -> dict[int, float]:
    """Compute Sonneborn-Berger: opponent points weighted by achieved score."""
    totals: dict[int, float] = defaultdict(float)
    for match in matches:
        if match.opponent_id is None:
            continue
        totals[match.player_id] += points.get(match.opponent_id, 0.0) * match.score
    return dict(totals)
