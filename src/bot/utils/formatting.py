"""User-facing text formatting helpers."""

from __future__ import annotations


def format_points(points: float) -> str:
    """Format score values with chess-friendly half-point notation."""
    if points.is_integer():
        return str(int(points))
    return f"{points:.1f}".replace(".5", "½")
