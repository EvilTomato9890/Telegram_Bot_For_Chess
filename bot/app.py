"""Application factory and dependency container."""

from __future__ import annotations

from dataclasses import dataclass

from infra.config import AppConfig, load_config
from infra.logging import AuditLogger, setup_logging
from repositories import (
    GameRepository,
    PlayerRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
)
from services import (
    AccessControlService,
    NotificationService,
    PairingService,
    RegistrationService,
    ResultReportingService,
    ScoringService,
    TicketService,
    TournamentService,
)


@dataclass(slots=True)
class Container:
    """Simple DI container for app dependencies."""

    config: AppConfig
    audit_logger: AuditLogger
    tournament_service: TournamentService
    registration_service: RegistrationService
    pairing_service: PairingService
    scoring_service: ScoringService
    result_reporting_service: ResultReportingService
    ticket_service: TicketService
    notification_service: NotificationService
    access_control_service: AccessControlService


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

    tournament_repository = TournamentRepository()
    player_repository = PlayerRepository()
    round_repository = RoundRepository()
    table_repository = TableRepository()
    game_repository = GameRepository()
    ticket_repository = TicketRepository()

    notification_service = NotificationService()
    access_control_service = AccessControlService.from_config(
        admin_ids=config.admin_ids,
        arbitrs_ids=config.arbitrs_ids,
    )
    scoring_service = ScoringService(
        player_repository=player_repository,
        round_repository=round_repository,
        game_repository=game_repository,
    )

    return Container(
        config=config,
        audit_logger=audit_logger,
        tournament_service=TournamentService(tournament_repository=tournament_repository),
        registration_service=RegistrationService(
            player_repository=player_repository,
            tournament_repository=tournament_repository,
        ),
        pairing_service=PairingService(
            tournament_repository=tournament_repository,
            round_repository=round_repository,
            table_repository=table_repository,
            game_repository=game_repository,
        ),
        scoring_service=scoring_service,
        result_reporting_service=ResultReportingService(
            game_repository=game_repository,
            round_repository=round_repository,
            scoring_service=scoring_service,
            notification_service=notification_service,
            access_control_service=access_control_service,
        ),
        ticket_service=TicketService(
            ticket_repository=ticket_repository,
            audit_logger=audit_logger,
            arbitrs_ids=config.arbitrs_ids,
            organizer_ids=config.admin_ids,
        ),
        notification_service=notification_service,
        access_control_service=access_control_service,
    )


def create_app() -> BotApplication:
    return BotApplication(container=create_container())


__all__ = ["Container", "BotApplication", "create_app", "create_container"]
