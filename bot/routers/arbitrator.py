"""Arbitrator command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext


def build_arbitrator_router(context: RouterContext) -> Router:
    """Create arbitrator router."""

    router = Router(name="arbitrator")
    acl = context.acl_service
    result_service = context.result_service
    notification_service = context.notification_service
    audit_logger = context.audit_logger

    @router.message(Command("approve_result"))
    async def approve_result_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/approve_result")
        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.answer("Формат: /approve_result <game_id> <result>")
            return
        game_id = int(parts[1])
        result = parts[2]
        result_service.approve_result(game_id=game_id, raw_result=result)
        audit_logger.log_event(
            actor_id=message.from_user.id,
            roles=[role.value for role in acl.resolve_roles(message.from_user.id)],
            command="/approve_result",
            entity=f"game:{game_id}",
            before=None,
            after={"result": result},
            result="ok",
            reason=None,
        )
        await message.answer(f"Результат игры {game_id} подтвержден.")
        for item in notification_service.flush():
            await message.answer(item)

    return router
