"""Application factory and dependency container."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from handlers import HelpCommandHandler, RoleCommandHandler, TicketCommandHandler
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
        try:
            asyncio.run(self._run_polling())
        except KeyboardInterrupt:
            self.container.audit_logger.log_event(
                actor="system",
                command="shutdown",
                entity="application",
                action="interrupt",
                result="ok",
            )

    async def _run_polling(self) -> None:
        router = Router()
        self._register_handlers(router)

        dispatcher = Dispatcher()
        dispatcher.include_router(router)

        bot = Bot(token=self.container.config.token)
        try:
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()

    def _register_handlers(self, router: Router) -> None:
        help_handler = HelpCommandHandler(access_control_service=self.container.access_control_service)
        role_handler = RoleCommandHandler(access_control_service=self.container.access_control_service)
        ticket_handler = TicketCommandHandler(
            ticket_service=self.container.ticket_service,
            access_control_service=self.container.access_control_service,
        )

        @router.message(Command("start"))
        async def start_handler(message: Message) -> None:
            await message.answer("Bot is running. Use /help to list available commands.")

        @router.message(Command("help"))
        async def help_command_handler(message: Message) -> None:
            actor_id = self._actor_id(message)
            await message.answer(help_handler.handle_help(actor_id=actor_id))

        @router.message(Command("grant_role"))
        async def grant_role_command_handler(message: Message) -> None:
            await self._dispatch_command(
                message=message,
                handler=lambda actor_id, raw_command: role_handler.handle_grant(
                    actor_id=actor_id,
                    raw_command=raw_command,
                ),
            )

        @router.message(Command("revoke_role"))
        async def revoke_role_command_handler(message: Message) -> None:
            await self._dispatch_command(
                message=message,
                handler=lambda actor_id, raw_command: role_handler.handle_revoke(
                    actor_id=actor_id,
                    raw_command=raw_command,
                ),
            )

        @router.message(Command("create_ticket"))
        async def create_ticket_command_handler(message: Message) -> None:
            await self._dispatch_command(
                message=message,
                handler=lambda actor_id, raw_command: ticket_handler.handle_create_ticket(
                    actor_id=actor_id,
                    raw_command=raw_command,
                ),
            )

        @router.message(Command("close_ticket"))
        async def close_ticket_command_handler(message: Message) -> None:
            await self._dispatch_command(
                message=message,
                handler=lambda actor_id, raw_command: ticket_handler.handle_close_ticket(
                    actor_id=actor_id,
                    raw_command=raw_command,
                ),
            )

    async def _dispatch_command(self, message: Message, handler: Callable[[int, str], str]) -> None:
        try:
            actor_id = self._actor_id(message)
            raw_command = self._raw_text(message)
            response = handler(actor_id, raw_command)
        except PermissionError as exc:
            await message.answer(f"Access denied: {exc}")
        except ValueError as exc:
            await message.answer(f"Invalid command: {exc}")
        except Exception:
            logging.getLogger(__name__).exception("Unhandled command error")
            await message.answer("Internal error while handling command.")
        else:
            await message.answer(response)

    @staticmethod
    def _raw_text(message: Message) -> str:
        return message.text or ""

    @staticmethod
    def _actor_id(message: Message) -> int:
        if message.from_user is None:
            raise ValueError("actor cannot be resolved for system messages")
        return message.from_user.id


def create_container(dotenv_path: str | Path | None = None) -> Container:
    if dotenv_path is None:
        resolved_dotenv_path: str | Path = Path(__file__).resolve().parent.parent / ".env"
    else:
        resolved_dotenv_path = dotenv_path
    config = load_config(resolved_dotenv_path)
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
            access_control_service=access_control_service,
        ),
        notification_service=notification_service,
        access_control_service=access_control_service,
    )


def create_app(dotenv_path: str | Path | None = None) -> BotApplication:
    return BotApplication(container=create_container(dotenv_path=dotenv_path))


__all__ = ["Container", "BotApplication", "create_app", "create_container"]
