"""Application factory and dependency container."""

from __future__ import annotations

from dataclasses import dataclass

from infra.config import AppConfig, load_config
from infra.logging import AuditLogger, setup_logging
from services import PairingService, TicketService, TournamentService


@dataclass(slots=True)
class Container:
    """Simple DI container for app dependencies."""

    config: AppConfig
    audit_logger: AuditLogger
    tournament_service: TournamentService
    pairing_service: PairingService
    ticket_service: TicketService


@dataclass(slots=True)
class BotApplication:
    """Entrypoint object for bot runtime."""

    container: Container

    def run(self) -> None:
        self.container.audit_logger.log_event(
            actor="system",
            command="startup",
            entity="application",
            action="initialize",
            result="ok",
        )


def create_container() -> Container:
    config = load_config()
    audit_logger = setup_logging(level=config.log_level, audit_log_path=config.audit_log_path)

    return Container(
        config=config,
        audit_logger=audit_logger,
        tournament_service=TournamentService(),
        pairing_service=PairingService(),
        ticket_service=TicketService(),
    )


def create_app() -> BotApplication:
    return BotApplication(container=create_container())


__all__ = ["Container", "BotApplication", "create_app", "create_container"]
