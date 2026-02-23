"""Application bootstrap for Telegram Swiss tournament bot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types.error_event import ErrorEvent
from bot.routers import (
    build_arbitrator_router,
    build_common_router,
    build_organizer_router,
    build_player_router,
)
from infra import AppConfig, AuditLogger, Database, load_config, setup_logging
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


@dataclass(slots=True)
class Container:
    """Dependency container for all app components."""

    config: AppConfig
    database: Database
    audit_logger: AuditLogger
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

    def as_context(self) -> dict[str, Any]:
        """Flat dictionary used by routers."""

        return {
            "config": self.config,
            "audit_logger": self.audit_logger,
            "acl_service": self.acl_service,
            "notification_service": self.notification_service,
            "scoring_service": self.scoring_service,
            "registration_service": self.registration_service,
            "tournament_service": self.tournament_service,
            "pairing_service": self.pairing_service,
            "result_service": self.result_service,
            "ticket_service": self.ticket_service,
            "undo_service": self.undo_service,
            "player_repo": self.player_repo,
            "round_repo": self.round_repo,
            "game_repo": self.game_repo,
            "table_repo": self.table_repo,
        }


@dataclass(slots=True)
class BotApplication:
    """Runtime entrypoint."""

    container: Container

    def run(self) -> None:
        """Run long-polling."""

        self.container.audit_logger.log_event(
            actor_id="system",
            roles=["system"],
            command="startup",
            entity="application",
            before=None,
            after={"state": "polling"},
            result="ok",
            reason=None,
        )
        try:
            asyncio.run(self._run_polling())
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Polling interrupted by user.")

    async def _run_polling(self) -> None:
        dispatcher = Dispatcher()
        context = self.container.as_context()
        dispatcher.include_router(build_common_router(context))
        dispatcher.include_router(build_player_router(context))
        dispatcher.include_router(build_arbitrator_router(context))
        dispatcher.include_router(build_organizer_router(context))

        @dispatcher.errors()
        async def global_error_handler(event: ErrorEvent) -> None:
            exception = event.exception
            update = event.update
            logging.getLogger(__name__).exception("Unhandled update error: %s", exception)
            self.container.audit_logger.log_event(
                actor_id="unknown",
                roles=["unknown"],
                command="update",
                entity="dispatcher",
                before={"update_id": update.update_id if update else None},
                after=None,
                result="error",
                reason=str(exception),
            )
            if isinstance(exception, ValueError) and update.message is not None:
                await update.message.answer(f"Ошибка: {exception}")
            elif isinstance(exception, PermissionError) and update.message is not None:
                await update.message.answer("Недостаточно прав для этой команды.")
            elif update.message is not None:
                await update.message.answer("Внутренняя ошибка обработки команды.")

        bot = Bot(token=self.container.config.token)
        try:
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()


def create_container(dotenv_path: str | Path | None = None) -> Container:
    """Build and wire app dependencies."""

    resolved = Path(dotenv_path) if dotenv_path is not None else Path(__file__).resolve().parent.parent / ".env"
    config = load_config(resolved)
    audit_logger = setup_logging(level=config.log_level, audit_log_path=config.audit_log_path)
    init_db(config.db_url)

    database = Database(config.db_url)
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
        admin_ids=set(config.admin_ids),
        arbitrs_ids=set(config.arbitrs_ids),
        role_grants_repo=role_repo,
        player_repo=player_repo,
    )
    notification_service = NotificationService()
    scoring_service = ScoringService(player_repo=player_repo, round_repo=round_repo, game_repo=game_repo)
    registration_service = RegistrationService(
        player_repo=player_repo,
        tournament_repo=tournament_repo,
        table_repo=table_repo,
    )
    tournament_service = TournamentService(
        tournament_repo=tournament_repo,
        table_repo=table_repo,
        round_repo=round_repo,
        player_repo=player_repo,
        game_repo=game_repo,
        ticket_repo=ticket_repo,
        report_repo=report_repo,
        default_rules=config.default_rules,
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
        audit_logger=audit_logger,
    )
    undo_service = UndoService(
        database=database,
        undo_repo=undo_repo,
        acl_service=acl_service,
        audit_logger=audit_logger,
    )

    tournament_service.ensure_tournament()

    return Container(
        config=config,
        database=database,
        audit_logger=audit_logger,
        tournament_repo=tournament_repo,
        player_repo=player_repo,
        round_repo=round_repo,
        game_repo=game_repo,
        report_repo=report_repo,
        table_repo=table_repo,
        ticket_repo=ticket_repo,
        role_repo=role_repo,
        undo_repo=undo_repo,
        acl_service=acl_service,
        notification_service=notification_service,
        scoring_service=scoring_service,
        registration_service=registration_service,
        tournament_service=tournament_service,
        pairing_service=pairing_service,
        result_service=result_service,
        ticket_service=ticket_service,
        undo_service=undo_service,
    )


def create_app(dotenv_path: str | Path | None = None) -> BotApplication:
    """Create runnable app object."""

    return BotApplication(container=create_container(dotenv_path))


__all__ = ["Container", "BotApplication", "create_container", "create_app"]
