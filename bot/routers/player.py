"""Player-specific command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext


def build_player_router(context: RouterContext) -> Router:
    """Create player router."""

    router = Router(name="player")
    acl = context.acl_service
    registration_service = context.registration_service
    audit_logger = context.audit_logger

    @router.message(Command("register"))
    async def register_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/register")
        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 4:
            await message.answer("Формат: /register <username_or_user_id|me> <рейтинг> <имя>")
            return
        id_or_username = parts[1].strip()
        rating = int(parts[2])
        full_name = parts[3].strip()
        if id_or_username == "me":
            telegram_id = message.from_user.id
            username = message.from_user.username
        elif id_or_username.startswith("@"):
            telegram_id = message.from_user.id
            username = id_or_username[1:]
        else:
            telegram_id = int(id_or_username)
            username = message.from_user.username

        player = registration_service.register(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            rating=rating,
        )
        audit_logger.log_event(
            actor_id=message.from_user.id,
            roles=[role.value for role in acl.resolve_roles(message.from_user.id)],
            command="/register",
            entity=f"player:{player.id}",
            before=None,
            after={"telegram_id": player.telegram_id, "rating": player.rating},
            result="ok",
            reason=None,
        )
        await message.answer(f"Регистрация успешна: #{player.id} {player.full_name}, рейтинг {player.rating}.")

    return router
