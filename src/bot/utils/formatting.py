"""User-facing text formatting helpers."""

from __future__ import annotations


def format_points(points: float) -> str:
    """Format score values with chess-friendly half-point notation."""
    if points.is_integer():
        return str(int(points))
    return f"{points:.1f}".replace(".5", "½")


def format_round_game(
    *,
    round_number: int,
    table_number: int,
    color: str,
    opponent: str,
    location: str | None,
    seat: str | None = None,
) -> str:
    """Format one game line for `/my_next` and `/round <n>` responses."""
    location_text = location or "не указана"
    seat_suffix = f", место {seat}" if seat else ""
    return (
        f"Тур {round_number}: стол {table_number}{seat_suffix}, "
        f"цвет {color}, соперник {opponent}, локация: {location_text}"
    )
