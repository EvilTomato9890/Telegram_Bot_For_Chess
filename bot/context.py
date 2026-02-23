"""Typed router context shared by all handler factories."""

from __future__ import annotations

from dataclasses import dataclass

from infra import AppConfig, AuditLogger
from repositories import GameRepository, PlayerRepository, RoundRepository, TableRepository
from services import (
    AccessControlService,
    NotificationService,
    PairingService,
    RegistrationService,
    ResultService,
    ScoringService,
    TicketService,
    TournamentService,
    UndoService,
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
    undo_service: UndoService
    player_repo: PlayerRepository
    round_repo: RoundRepository
    game_repo: GameRepository
    table_repo: TableRepository

