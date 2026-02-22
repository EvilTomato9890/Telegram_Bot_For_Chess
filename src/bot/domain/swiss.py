"""Swiss pairing and tie-break domain logic.

This module intentionally stays framework-agnostic so algorithms can be reused
from handlers, background jobs, or tests.
"""

from __future__ import annotations

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


def swiss_pairings(player_ids: list[int]) -> list[tuple[int, int | None]]:
    """Build naive Swiss pairings by neighboring ranks.

    The function pairs top-down by adjacent positions and assigns a bye if odd.
    This baseline can be replaced later with color-balance and rematch control.
    """
    ordered = list(player_ids)
    pairs: list[tuple[int, int | None]] = []

    while len(ordered) >= 2:
        pairs.append((ordered.pop(0), ordered.pop(0)))

    if ordered:
        pairs.append((ordered.pop(0), None))

    return pairs
