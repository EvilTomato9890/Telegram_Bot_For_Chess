"""Reusable DTOs for command handlers and services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleCommand:
    actor_id: int
    target_user_id: int
    role: str


@dataclass(frozen=True, slots=True)
class ServiceResponse:
    ok: bool
    message: str


__all__ = ["RoleCommand", "ServiceResponse"]
