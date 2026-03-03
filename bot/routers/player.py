"""Player-specific command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext
from domain.exceptions import DomainError


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
        registration_service.validate_self_registration_precheck(message.from_user.id)

        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: /register <рейтинг> <имя и фамилия>")
            return
        try:
            rating = int(parts[1])
        except ValueError as exc:
            raise DomainError("Рейтинг должен быть целым числом.") from exc
        full_name = parts[2].strip()
        if not full_name:
            raise DomainError("Имя и фамилия не могут быть пустыми.")

        player = registration_service.register(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
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
