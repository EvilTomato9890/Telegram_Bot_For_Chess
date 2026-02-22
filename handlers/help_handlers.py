"""Help command handler with ACL-aware command aggregation."""

from __future__ import annotations

from services import AccessControlService


class HelpCommandHandler:
    """Build /help output by aggregating all commands allowed for a user."""

    def __init__(self, access_control_service: AccessControlService) -> None:
        self._access_control_service = access_control_service

    def handle_help(self, actor_id: int) -> str:
        commands = self._access_control_service.allowed_commands(actor_id)
        if not commands:
            return "Доступных команд нет."
        return "Доступные команды:\n" + "\n".join(commands)
