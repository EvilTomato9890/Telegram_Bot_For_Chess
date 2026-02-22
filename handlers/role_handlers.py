"""Command handlers for role administration."""

from __future__ import annotations

from handlers.acl import acl_required
from schemas import RoleCommand
from services import AccessControlService
from validators import parse_positive_int, validate_role


class RoleCommandHandler:
    """Thin handler: parse, service call, and response formatting."""

    def __init__(self, access_control_service: AccessControlService) -> None:
        self._access_control_service = access_control_service

    @acl_required("/grant_role")
    def handle_grant(self, actor_id: int, raw_command: str) -> str:
        command = self._parse_role_command(actor_id=actor_id, raw_command=raw_command)
        result = self._access_control_service.grant_role(
            actor_id=command.actor_id,
            target_user_id=command.target_user_id,
            role=command.role,
        )
        return self._format_response(result.message)

    @acl_required("/revoke_role")
    def handle_revoke(self, actor_id: int, raw_command: str) -> str:
        command = self._parse_role_command(actor_id=actor_id, raw_command=raw_command)
        result = self._access_control_service.revoke_role(
            actor_id=command.actor_id,
            target_user_id=command.target_user_id,
            role=command.role,
        )
        return self._format_response(result.message)

    def _parse_role_command(self, actor_id: int, raw_command: str) -> RoleCommand:
        parts = raw_command.split()
        if len(parts) != 3:
            raise ValueError("expected format: /command <user_id> <role>")

        target_user_id = parse_positive_int(parts[1], field_name="user_id")
        role = validate_role(parts[2])
        return RoleCommand(actor_id=actor_id, target_user_id=target_user_id, role=role)

    def _format_response(self, message: str) -> str:
        return f"✅ {message}"


__all__ = ["RoleCommandHandler"]
