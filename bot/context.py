"""Typed router context shared by all handler factories."""

from __future__ import annotations

from dataclasses import dataclass

from infra import AppConfig, AuditLogger
from repositories import GameRepository, PlayerRepository, RoundRepository, TableRepository
from services import (
    AccessControlService,
    NotificationGateway,
    NotificationService,
    PairingService,
    RegistrationService,
    ResultService,
    ScoringService,
    TicketService,
    TournamentService,
)


@dataclass(slots=True, frozen=True)
class RouterContext:
    """All dependencies needed by aiogram routers."""

    config: AppConfig
    audit_logger: AuditLogger
    acl_service: AccessControlService
    notification_service: NotificationService
    scoring_service: ScoringService
    registration_service: RegistrationService
    tournament_service: TournamentService
    pairing_service: PairingService
    result_service: ResultService
    ticket_service: TicketService
    player_repo: PlayerRepository
    round_repo: RoundRepository
    game_repo: GameRepository
    table_repo: TableRepository
    notification_gateway: NotificationGateway | None = None
