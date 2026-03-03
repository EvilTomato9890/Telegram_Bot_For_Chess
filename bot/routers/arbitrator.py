"""Arbitrator command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext
from domain.exceptions import DomainError


def build_arbitrator_router(context: RouterContext) -> Router:
    """Create arbitrator router."""

    router = Router(name="arbitrator")
    acl = context.acl_service
    result_service = context.result_service
    ticket_service = context.ticket_service
    notification_gateway = context.notification_gateway
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
        try:
            game_id = int(parts[1])
        except ValueError as exc:
            raise DomainError("game_id должен быть числом.") from exc
        result = parts[2]
        outcome = result_service.approve_result(game_id=game_id, raw_result=result)
        audit_logger.log_event(
            actor_id=message.from_user.id,
            roles=[role.value for role in acl.resolve_roles(message.from_user.id)],
            command="/approve_result",
            entity=f"game:{game_id}",
            before=None,
            after={"result": outcome.confirmed_result},
            result="ok",
            reason=None,
        )
        await message.answer(outcome.message)

        bot = message.bot
        if bot is not None:
            schedule_hint = outcome.next_round_hint or "Время следующего тура пока не назначено."
            notify_text = (
                f"Арбитр подтвердил результат игры {outcome.game_id}: "
                f"{outcome.confirmed_result}. {schedule_hint}"
            )
            for target in (outcome.white_telegram_id, outcome.black_telegram_id):
                if not isinstance(target, int):
                    continue
                if notification_gateway is not None:
                    await notification_gateway.send_to_user(bot, target, notify_text)
                    continue
                try:
                    await bot.send_message(target, notify_text)
                except Exception:  # noqa: BLE001
                    continue

    @router.message(Command("ticket_queue"))
    async def ticket_queue_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/ticket_queue")
        tickets = ticket_service.ticket_queue_for_arbitrator(message.from_user.id)
        if not tickets:
            await message.answer("Очередь тикетов пуста.")
            return
        lines = []
        for ticket in tickets:
            lines.append(
                (
                    f"#{ticket.id} | type={ticket.ticket_type.value} | status={ticket.status.value} | "
                    f"author={ticket.author_telegram_id} | assignee={ticket.assignee_telegram_id or '-'} | "
                    f"opened={ticket.opened_at.isoformat()} | {ticket.description}"
                )
            )
        await message.answer("Текущая очередь тикетов:\n" + "\n".join(lines))

    return router
