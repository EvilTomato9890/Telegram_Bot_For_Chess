"""Reusable validators shared across role commands."""

from __future__ import annotations

_VALID_ROLES = {"player", "arbiter", "admin"}


def parse_positive_int(raw_value: str, field_name: str) -> int:
    """Parse positive integer from text command part."""

    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc

    if parsed <= 0:
        raise ValueError(f"{field_name} must be positive")

    return parsed


def validate_role(role: str) -> str:
    """Normalize and validate role token."""

    normalized = role.strip().lower()
    if normalized not in _VALID_ROLES:
        allowed = ", ".join(sorted(_VALID_ROLES))
        raise ValueError(f"role must be one of: {allowed}")
    return normalized


__all__ = ["parse_positive_int", "validate_role"]
