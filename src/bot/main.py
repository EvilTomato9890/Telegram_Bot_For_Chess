"""Application entry point.

The entrypoint wires configuration, logging, database infrastructure and bot
routers. It also registers a global error handler for user-friendly responses.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.types import ErrorEvent
from loguru import logger

from bot.config import get_settings
from bot.db.migrations import initialize_database
from bot.handlers.organizer import router as organizer_router
from bot.handlers.player import router as player_router
from bot.logging import configure_logger
from bot.services.acl import AccessControlService


def build_dispatcher(acl: AccessControlService) -> Dispatcher:
    """Build dispatcher with routers and global exception handler."""
    dispatcher = Dispatcher()
    root_router = Router(name="root")
    root_router.include_router(player_router)
    root_router.include_router(organizer_router)

    @root_router.error()
    async def on_error(event: ErrorEvent) -> bool:
        """Handle unexpected exceptions with friendly text + detailed logs."""
        logger.exception("Unhandled exception while processing update", exc_info=event.exception)
        if event.update.message is not None:
            await event.update.message.answer(
                "Произошла внутренняя ошибка. Мы уже записали проблему в лог и скоро исправим её."
            )
        return True

    dispatcher.include_router(root_router)
    dispatcher[AccessControlService] = acl
    return dispatcher


async def run() -> None:
    """Start bot polling loop with configured dependencies."""
    settings = get_settings()
    configure_logger(settings.log_level)

    await initialize_database(settings.database_url)

    acl = AccessControlService(admin_ids=set(settings.admin_ids))
    bot = Bot(token=settings.token)
    dispatcher = build_dispatcher(acl=acl)

    logger.info("Starting bot polling")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
