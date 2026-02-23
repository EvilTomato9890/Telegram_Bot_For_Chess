"""Common routes shared by all roles."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.context import RouterContext
from domain.models import Role, TicketType
from keyboards import player_menu_keyboard, report_keyboard, start_keyboard


def build_common_router(context: RouterContext) -> Router:
    """Create router with shared commands."""

    router = Router(name="common")
    acl = context.acl_service
    tournament_service = context.tournament_service
    scoring_service = context.scoring_service
    result_service = context.result_service
    ticket_service = context.ticket_service
    audit_logger = context.audit_logger
    player_repo = context.player_repo
    game_repo = context.game_repo
    round_repo = context.round_repo
    table_repo = context.table_repo
    notification_service = context.notification_service
    default_top = context.config.standings_default_top

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        if message.from_user is None:
            return
        text = (
            "Добро пожаловать в бота шахматного турнира.\n"
            "Используйте кнопки ниже: регистрация и доступ к меню турнира."
        )
        await message.answer(text, reply_markup=start_keyboard())

    @router.callback_query(F.data == "start:register")
    async def start_register_callback(callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.answer(
                "Для регистрации используйте команду:\n"
                "/register me <рейтинг> <Имя Фамилия>\n"
                "Пример: /register me 1500 Иван Иванов"
            )
        await callback.answer()

    @router.callback_query(F.data == "start:my_tournament")
    async def start_tournament_menu_callback(callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.answer("Открываю меню турнира.", reply_markup=player_menu_keyboard())
        await callback.answer()

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        if message.from_user is None:
            return
        view = acl.help_for(message.from_user.id)
        if not view.commands:
            await message.answer("Нет доступных команд.")
            return
        lines = [f"{spec.name} - {spec.description}" for spec in sorted(view.commands, key=lambda item: item.name)]
        await message.answer("Доступные команды:\n" + "\n".join(lines))

    @router.message(Command("rules"))
    async def rules_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/rules")
        tournament = tournament_service.ensure_tournament()
        await message.answer(tournament.rules_text or "Правила пока не заданы.")

    @router.message(Command("standings"))
    async def standings_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/standings")
        parts = (message.text or "").split()
        try:
            top_n = default_top if len(parts) < 2 else int(parts[1])
        except ValueError as exc:
            raise ValueError("Формат: /standings [top_n]") from exc
        rows = scoring_service.standings(top_n)
        player_position = None
        for row in scoring_service.recalculate():
            if row.telegram_id == message.from_user.id:
                player_position = row.position
                break
        lines = [
            (
                f"{row.position}. {row.full_name} - {row.score} "
                f"(BH {row.buchholz}, MBH {row.median_buchholz}, SB {row.sonneborn_berger})"
            )
            for row in rows
        ]
        suffix = f"\nВаша позиция: {player_position}" if player_position is not None else ""
        await message.answer("Таблица лидеров:\n" + "\n".join(lines) + suffix)

    @router.message(Command("schedule"))
    async def schedule_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/schedule")
        rounds = round_repo.list_all()
        if not rounds:
            await message.answer("Туры пока не созданы.")
            return
        lines = []
        for round_ in rounds:
            starts = round_.starts_at.isoformat() if round_.starts_at else "-"
            ends = round_.window_end_at.isoformat() if round_.window_end_at else "-"
            lines.append(f"Тур {round_.number}: статус={round_.status.value}, окно={starts}..{ends}")
        await message.answer("\n".join(lines))

    @router.message(Command("close_ticket"))
    async def close_ticket_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/close_ticket")
        roles = acl.resolve_roles(message.from_user.id)
        parts = (message.text or "").split()
        ticket_id: int | None = None
        if len(parts) > 1:
            try:
                ticket_id = int(parts[1])
            except ValueError as exc:
                raise ValueError("Формат: /close_ticket <ticket_id>") from exc
        elif Role.ARBITRATOR in roles or Role.ADMIN in roles:
            if Role.PLAYER not in roles:
                raise ValueError("Для арбитра/админа используйте /close_ticket <ticket_id>.")
        closed = ticket_service.close_ticket(actor_id=message.from_user.id, ticket_id=ticket_id)
        await message.answer(f"Тикет #{closed.id} закрыт.")

    @router.message(Command("create_ticket"))
    async def create_ticket_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/create_ticket")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2:
            raise ValueError("Формат: /create_ticket <arbitr|organizer> <описание>")
        try:
            ticket_type = TicketType(parts[1].strip().lower())
        except ValueError as exc:
            raise ValueError("Тип тикета должен быть arbitr или organizer.") from exc
        description = parts[2] if len(parts) > 2 else "Без описания"
        ticket = ticket_service.create_ticket(
            actor_id=message.from_user.id,
            ticket_type=ticket_type,
            description=description,
        )
        assignee = ticket.assignee_telegram_id or "не назначен"
        await message.answer(f"Тикет #{ticket.id} создан. Исполнитель: {assignee}.")

    @router.message(Command("report"))
    async def report_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/report")
        await message.answer("Выберите результат партии:", reply_markup=report_keyboard())

    @router.callback_query(F.data.startswith("report:"))
    async def report_callback_handler(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            return
        acl.require(callback.from_user.id, "/report")
        token = (callback.data or "").split(":", maxsplit=1)[1]
        outcome = result_service.submit_player_report(callback.from_user.id, token)
        audit_logger.log_event(
            actor_id=callback.from_user.id,
            roles=[role.value for role in acl.resolve_roles(callback.from_user.id)],
            command="/report",
            entity=f"game:{outcome.game_id}",
            before=None,
            after={"status": outcome.status},
            result="ok",
            reason=None,
        )
        if callback.message is not None:
            await callback.message.answer(f"Игра {outcome.game_id}: {outcome.message}")
            for notification in notification_service.flush():
                await callback.message.answer(notification)
        await callback.answer()

    @router.message(Command("my_score"))
    async def my_score_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/my_score")
        row = scoring_service.my_score(message.from_user.id)
        await message.answer(
            (
                f"Очки: {row.score}\n"
                f"Buchholz: {row.buchholz}\n"
                f"Median Buchholz: {row.median_buchholz}\n"
                f"SB: {row.sonneborn_berger}\n"
                f"Позиция: {row.position}"
            )
        )

    @router.message(Command("get_game_id"))
    async def get_game_id_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/get_game_id")
        player = player_repo.get_by_telegram_id(message.from_user.id)
        if player is None or player.id is None:
            await message.answer("Вы не зарегистрированы.")
            return
        games = game_repo.list_by_player(player.id)
        if not games:
            await message.answer("Партии не найдены.")
            return
        unresolved = [game for game in games if game.result is None]
        target = unresolved[0] if unresolved else games[0]
        await message.answer(f"ID вашей последней/текущей партии: {target.id}")

    @router.message(Command("my_next"))
    async def my_next_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/my_next")
        player = player_repo.get_by_telegram_id(message.from_user.id)
        if player is None or player.id is None:
            await message.answer("Вы не зарегистрированы.")
            return
        games = game_repo.list_by_player(player.id)
        current = next((game for game in games if game.result is None), None)
        if current is None:
            await message.answer("Следующая партия пока не назначена.")
            return
        round_ = round_repo.get_by_id(current.round_id)
        if round_ is None:
            await message.answer("Ошибка данных тура.")
            return
        is_white = current.white_player_id == player.id
        opponent_id = current.black_player_id if is_white else current.white_player_id
        opponent = player_repo.get_by_id(opponent_id)
        table = table_repo.get_by_number(current.board_number)
        opponent_name = opponent.full_name if opponent else f"id={opponent_id}"
        location = table.location if table else "неизвестно"
        place = table.place_hint if table and table.place_hint else "без уточнения"
        await message.answer(
            (
                f"Тур {round_.number}, стол {current.board_number}, "
                f"цвет {'White' if is_white else 'Black'}, "
                f"соперник {opponent_name}, локация: {location}, место: {place}"
            )
        )

    return router

