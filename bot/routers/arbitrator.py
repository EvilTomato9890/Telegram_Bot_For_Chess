"""Arbitrator command handlers."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext
from domain.dto import PairingOutcome
from domain.exceptions import DomainError, OrganizerConfirmationRequiredError
from domain.models import PlayerStatus, Role


def build_arbitrator_router(context: RouterContext) -> Router:
    """Create arbitrator router."""

    router = Router(name="arbitrator")
    acl = context.acl_service
    result_service = context.result_service
    pairing_service = context.pairing_service
    ticket_service = context.ticket_service
    player_repo = context.player_repo
    table_repo = context.table_repo
    notification_gateway = context.notification_gateway
    audit_logger = context.audit_logger

    async def notify_user(bot: Bot | None, telegram_id: int, text: str) -> None:
        if notification_gateway is not None:
            await notification_gateway.send_to_user(bot, telegram_id, text)
            return
        if bot is None:
            return
        try:
            await bot.send_message(telegram_id, text)
        except Exception:  # noqa: BLE001
            return

    async def notify_admins(bot: Bot | None, text: str) -> None:
        for admin_id in acl.user_ids_with_role(Role.ADMIN):
            await notify_user(bot, admin_id, text)

    async def notify_admins_round_ready(bot: Bot | None, round_number: int | None) -> None:
        if round_number is None:
            return
        await notify_admins(bot, f"Все партии тура {round_number} завершены. Можно выполнять /end_round.")

    async def notify_players_reseed(bot: Bot | None, outcome: PairingOutcome) -> None:
        messages: dict[int, str] = {}
        for game in outcome.games:
            table = table_repo.get_by_number(game.board_number)
            location = table.location if table is not None else "неизвестно"
            white = player_repo.get_by_id(game.white_player_id)
            black = player_repo.get_by_id(game.black_player_id)
            white_name = white.full_name if white is not None else f"id={game.white_player_id}"
            black_name = black.full_name if black is not None else f"id={game.black_player_id}"
            messages[game.white_player_id] = (
                f"Пересборка тура {outcome.round_number}: стол {game.board_number}, цвет White, "
                f"соперник {black_name}, локация: {location}"
            )
            messages[game.black_player_id] = (
                f"Пересборка тура {outcome.round_number}: стол {game.board_number}, цвет Black, "
                f"соперник {white_name}, локация: {location}"
            )
        if outcome.bye_player_id is not None:
            messages[outcome.bye_player_id] = (
                f"Пересборка тура {outcome.round_number}: в этом туре у вас bye (1 очко)."
            )

        for player in player_repo.list_all():
            if player.status != PlayerStatus.ACTIVE:
                continue
            text = messages.get(player.id or 0, f"Пересборка тура {outcome.round_number}: ожидайте назначение.")
            await notify_user(bot, player.telegram_id, text)

    @router.message(Command("approve_result"))
    async def approve_result_handler(message: Message) -> None:
        if message.from_user is None:
            return
        actor_id = message.from_user.id
        acl.require(actor_id, "/approve_result")
        parts = (message.text or "").split()
        if len(parts) not in {3, 4}:
            await message.answer("Формат: /approve_result <game_id> <result> [confirm]")
            return
        try:
            game_id = int(parts[1])
        except ValueError as exc:
            raise DomainError("game_id должен быть числом.") from exc
        result = parts[2]
        confirm_requested = len(parts) == 4
        if confirm_requested and parts[3].lower() != "confirm":
            await message.answer("Формат: /approve_result <game_id> <result> [confirm]")
            return

        roles = acl.resolve_roles(actor_id)
        is_admin = Role.ADMIN in roles
        if confirm_requested and not is_admin:
            raise DomainError("Подтверждение confirm доступно только организатору.")

        try:
            outcome = result_service.approve_result(
                game_id=game_id,
                raw_result=result,
                allow_prepared_override=confirm_requested and is_admin,
            )
        except OrganizerConfirmationRequiredError as exc:
            confirm_cmd = f"/approve_result {exc.game_id} {exc.raw_result} confirm"
            if is_admin:
                await message.answer(
                    "Изменение затрагивает уже подготовленный, но не запущенный тур.\n"
                    f"Подтвердите пересборку: {confirm_cmd}"
                )
                return

            await notify_admins(
                message.bot,
                (
                    f"Арбитр {actor_id} запросил изменение результата игры {exc.game_id} на {exc.raw_result}.\n"
                    "Следующий тур уже подготовлен, требуется подтверждение организатора.\n"
                    f"Команда подтверждения: {confirm_cmd}"
                ),
            )
            await message.answer(
                "Следующий тур уже подготовлен. Запрос отправлен организаторам для подтверждения пересборки."
            )
            return

        audit_logger.log_event(
            actor_id=actor_id,
            roles=[role.value for role in roles],
            command="/approve_result",
            entity=f"game:{game_id}",
            before=None,
            after={"result": outcome.confirmed_result, "reseed_required": outcome.reseed_required},
            result="ok",
            reason=None,
        )
        await message.answer(outcome.message)

        bot = message.bot
        schedule_hint = outcome.next_round_hint or "Время следующего тура пока не назначено."
        notify_text = (
            f"Арбитр подтвердил результат игры {outcome.game_id}: "
            f"{outcome.confirmed_result}. {schedule_hint}"
        )
        for target in (outcome.white_telegram_id, outcome.black_telegram_id):
            if not isinstance(target, int):
                continue
            await notify_user(bot, target, notify_text)

        if outcome.reseed_required:
            rebuilt = pairing_service.rebuild_prepared_round(1, actor_id)
            await notify_players_reseed(bot, rebuilt)
            await notify_admins(
                bot,
                (
                    f"Организатор подтвердил ретро-изменение результата игры {outcome.game_id}. "
                    f"Подготовленный тур {rebuilt.round_number} пересобран."
                ),
            )
            await message.answer(f"Подготовленный тур {rebuilt.round_number} пересобран, участники оповещены.")

        if outcome.round_closed:
            await notify_admins_round_ready(bot, outcome.round_number)

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
            author = player_repo.get_by_telegram_id(ticket.author_telegram_id)
            author_table = author.current_board if author is not None else None
            lines.append(
                (
                    f"#{ticket.id} | type={ticket.ticket_type.value} | status={ticket.status.value} | "
                    f"author={ticket.author_telegram_id} | assignee={ticket.assignee_telegram_id or '-'} | "
                    f"table={author_table if author_table is not None else 'unknown'} | "
                    f"opened={ticket.opened_at.isoformat()} | {ticket.description}"
                )
            )
        await message.answer("Текущая очередь тикетов:\n" + "\n".join(lines))

    return router
