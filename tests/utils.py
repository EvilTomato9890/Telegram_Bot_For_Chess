"""Test helper utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict
import uuid

from infra import Database
from infra.logging import setup_logging
from repositories import (
    GameReportRepository,
    GameRepository,
    PlayerRepository,
    RoleGrantRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
    UndoRepository,
    init_db,
)
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


class ServiceBundle(TypedDict):
    """Typed dictionary with test repositories/services."""

    database: Database
    tournament_repo: TournamentRepository
    player_repo: PlayerRepository
    round_repo: RoundRepository
    game_repo: GameRepository
    report_repo: GameReportRepository
    table_repo: TableRepository
    ticket_repo: TicketRepository
    role_repo: RoleGrantRepository
    undo_repo: UndoRepository
    acl_service: AccessControlService
    notification_service: NotificationService
    scoring_service: ScoringService
    registration_service: RegistrationService
    tournament_service: TournamentService
    pairing_service: PairingService
    result_service: ResultService
    ticket_service: TicketService
    undo_service: UndoService


def build_db_url(prefix: str = "test") -> str:
    """Create unique sqlite db path in repository-local data directory."""

    path = Path("data") / f"{prefix}_{uuid.uuid4().hex}.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def build_services(db_url: str) -> ServiceBundle:
    """Build repositories and services for tests."""

    init_db(db_url)
    database = Database(db_url)
    tournament_repo = TournamentRepository(database)
    player_repo = PlayerRepository(database)
    round_repo = RoundRepository(database)
    game_repo = GameRepository(database)
    report_repo = GameReportRepository(database)
    table_repo = TableRepository(database)
    ticket_repo = TicketRepository(database)
    role_repo = RoleGrantRepository(database)
    undo_repo = UndoRepository(database)

    acl_service = AccessControlService(
        admin_ids={9001},
        arbitrs_ids={9002},
        role_grants_repo=role_repo,
        player_repo=player_repo,
    )
    notification_service = NotificationService()
    scoring_service = ScoringService(player_repo, round_repo, game_repo)
    registration_service = RegistrationService(player_repo, tournament_repo, table_repo)
    tournament_service = TournamentService(
        tournament_repo=tournament_repo,
        table_repo=table_repo,
        round_repo=round_repo,
        player_repo=player_repo,
        game_repo=game_repo,
        ticket_repo=ticket_repo,
        report_repo=report_repo,
        default_rules="rules",
    )
    pairing_service = PairingService(
        tournament_repo=tournament_repo,
        player_repo=player_repo,
        round_repo=round_repo,
        game_repo=game_repo,
        table_repo=table_repo,
        scoring_service=scoring_service,
    )
    result_service = ResultService(
        player_repo=player_repo,
        round_repo=round_repo,
        game_repo=game_repo,
        report_repo=report_repo,
        scoring_service=scoring_service,
        notification_service=notification_service,
    )
    ticket_service = TicketService(
        ticket_repo=ticket_repo,
        acl_service=acl_service,
        audit_logger=setup_logging(audit_log_path="logs/test_audit.log"),
    )
    undo_service = UndoService(
        database=database,
        undo_repo=undo_repo,
        acl_service=acl_service,
        audit_logger=setup_logging(audit_log_path="logs/test_audit.log"),
    )
    tournament_service.ensure_tournament()
    return {
        "database": database,
        "tournament_repo": tournament_repo,
        "player_repo": player_repo,
        "round_repo": round_repo,
        "game_repo": game_repo,
        "report_repo": report_repo,
        "table_repo": table_repo,
        "ticket_repo": ticket_repo,
        "role_repo": role_repo,
        "undo_repo": undo_repo,
        "acl_service": acl_service,
        "notification_service": notification_service,
        "scoring_service": scoring_service,
        "registration_service": registration_service,
        "tournament_service": tournament_service,
        "pairing_service": pairing_service,
        "result_service": result_service,
        "ticket_service": ticket_service,
        "undo_service": undo_service,
    }

