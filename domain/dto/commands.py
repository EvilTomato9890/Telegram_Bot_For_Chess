"""DTOs used by command handlers and ACL registry."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models.enums import Role


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One command definition used for ACL and help output."""

    name: str
    roles: frozenset[Role]
    description: str
    group: str = "Прочее"


@dataclass(frozen=True, slots=True)
class HelpView:
    """Rendered command help grouped for one actor."""

    actor_id: int
    commands: tuple[CommandSpec, ...]
