"""Access control service and declarative ACL matrix."""

from __future__ import annotations

from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass

from schemas import ServiceResponse
from validators import validate_role

Role = str
Command = str


# Declarative ACL matrix: command -> roles that can execute it.
COMMAND_ACCESS_MATRIX: dict[Command, frozenset[Role]] = {
    "/grant_role": frozenset({"admin"}),
    "/revoke_role": frozenset({"admin"}),
    "/create_tournament": frozenset({"admin"}),
    "/set_status": frozenset({"admin"}),
    "/pairings": frozenset({"admin", "arbiter"}),
    "/report": frozenset({"player", "arbiter", "admin"}),
    "/report_result": frozenset({"admin", "arbiter"}),
    "/approve_result": frozenset({"admin", "arbiter"}),
    "/register": frozenset({"player", "arbiter", "admin"}),
    "/help": frozenset({"player", "arbiter", "admin"}),
}


@dataclass(frozen=True, slots=True)
class RoleSnapshot:
    """Merged roles for a specific user."""

    user_id: int
    roles: frozenset[Role]


class AccessControlService:
    """Role grants/revokes and permissions checks."""

    def __init__(
        self,
        *,
        config_roles_by_user: Mapping[int, AbstractSet[Role]] | None = None,
        db_roles_by_user: Mapping[int, AbstractSet[Role]] | None = None,
        command_access_matrix: Mapping[Command, AbstractSet[Role]] | None = None,
    ) -> None:
        self._config_roles_by_user: dict[int, set[Role]] = {
            user_id: {validate_role(role) for role in roles}
            for user_id, roles in (config_roles_by_user or {}).items()
        }
        self._db_roles_by_user: dict[int, set[Role]] = {
            user_id: {validate_role(role) for role in roles}
            for user_id, roles in (db_roles_by_user or {}).items()
        }
        source_matrix = command_access_matrix or COMMAND_ACCESS_MATRIX
        self._command_access_matrix: dict[Command, frozenset[Role]] = {
            command: frozenset(validate_role(role) for role in allowed_roles)
            for command, allowed_roles in source_matrix.items()
        }

    @classmethod
    def from_config(cls, *, admin_ids: list[int], arbitrs_ids: list[int]) -> AccessControlService:
        roles: dict[int, set[Role]] = {}
        for user_id in admin_ids:
            roles.setdefault(user_id, set()).add("admin")
        for user_id in arbitrs_ids:
            roles.setdefault(user_id, set()).add("arbiter")
        return cls(config_roles_by_user=roles)

    def grant_role(self, actor_id: int, target_user_id: int, role: str) -> ServiceResponse:
        del actor_id
        normalized_role = validate_role(role)
        roles = self._db_roles_by_user.setdefault(target_user_id, set())
        roles.add(normalized_role)
        return ServiceResponse(ok=True, message=f"role '{normalized_role}' granted to user {target_user_id}")

    def revoke_role(self, actor_id: int, target_user_id: int, role: str) -> ServiceResponse:
        del actor_id
        normalized_role = validate_role(role)
        roles = self._db_roles_by_user.setdefault(target_user_id, set())
        roles.discard(normalized_role)
        return ServiceResponse(ok=True, message=f"role '{normalized_role}' revoked for user {target_user_id}")

    def resolve_roles(self, user_id: int) -> RoleSnapshot:
        merged_roles = {*self._config_roles_by_user.get(user_id, set()), *self._db_roles_by_user.get(user_id, set())}
        return RoleSnapshot(user_id=user_id, roles=frozenset(merged_roles))

    def has_role(self, user_id: int, role: str) -> bool:
        normalized_role = validate_role(role)
        return normalized_role in self.resolve_roles(user_id).roles

    def has_any_role(self, user_id: int, roles: AbstractSet[Role]) -> bool:
        normalized_roles = {validate_role(role) for role in roles}
        if not normalized_roles:
            return False
        return bool(self.resolve_roles(user_id).roles.intersection(normalized_roles))

    def can_execute(self, user_id: int, command: Command) -> bool:
        allowed_roles = self._command_access_matrix.get(command)
        if allowed_roles is None:
            return False
        return self.has_any_role(user_id, allowed_roles)

    def allowed_commands(self, user_id: int) -> list[Command]:
        return sorted(
            command
            for command, allowed_roles in self._command_access_matrix.items()
            if self.has_any_role(user_id, allowed_roles)
        )
