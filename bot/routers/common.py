"""Common routes shared by all roles."""

from __future__ import annotations

from collections import defaultdict
import json

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.context import RouterContext
from domain.dto import CommandSpec
from domain.exceptions import DomainError
from domain.models import Role, TicketType, TournamentStatus
from keyboards import player_menu_keyboard, report_keyboard, start_keyboard


class RegistrationStates(StatesGroup):
    """FSM states for start-button registration flow."""

    waiting_rating = State()
    waiting_full_name = State()


def build_common_router(context: RouterContext) -> Router:
    """Create router with shared commands."""

    router = Router(name="common")
    acl = context.acl_service
    tournament_service = context.tournament_service
    scoring_service = context.scoring_service
    registration_service = context.registration_service
    result_service = context.result_service
    ticket_service = context.ticket_service
    audit_logger = context.audit_logger
    notification_gateway = context.notification_gateway
    player_repo = context.player_repo
    game_repo = context.game_repo
    round_repo = context.round_repo
    table_repo = context.table_repo
    default_top = context.config.standings_default_top

    async def notify_user(bot: Bot | None, telegram_id: int, text: str) -> bool:
        if notification_gateway is not None:
            return await notification_gateway.send_to_user(bot, telegram_id, text)
        if bot is None:
            return False
        try:
            await bot.send_message(telegram_id, text)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def notify_admins_round_ready(bot: Bot | None, round_number: int | None) -> None:
        if round_number is None:
            return
        text = f"Все партии тура {round_number} завершены. Можно выполнять /end_round."
        for admin_id in acl.user_ids_with_role(Role.ADMIN):
            await notify_user(bot, admin_id, text)

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
    async def start_register_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user is None:
            await callback.answer()
            return
        try:
            registration_service.validate_self_registration_precheck(callback.from_user.id)
        except DomainError as exc:
            await state.clear()
            if callback.message is not None:
                await callback.message.answer(f"Ошибка регистрации: {exc}")
            await callback.answer()
            return

        await state.clear()
        await state.set_state(RegistrationStates.waiting_rating)
        if callback.message is not None:
            await callback.message.answer("Введите ваш рейтинг (целое число, например 1500).")
        await callback.answer()

    @router.message(RegistrationStates.waiting_rating)
    async def register_rating_step(message: Message, state: FSMContext) -> None:
        raw_rating = (message.text or "").strip()
        try:
            rating = int(raw_rating)
        except ValueError:
            await message.answer("Рейтинг должен быть целым числом. Введите рейтинг еще раз.")
            return
        if rating < 0:
            await message.answer("Рейтинг не может быть отрицательным. Введите рейтинг еще раз.")
            return
        await state.update_data(rating=rating)
        await state.set_state(RegistrationStates.waiting_full_name)
        await message.answer("Введите имя и фамилию.")

    @router.message(RegistrationStates.waiting_full_name)
    async def register_full_name_step(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            await state.clear()
            return
        full_name = (message.text or "").strip()
        if not full_name:
            await message.answer("Имя не может быть пустым. Введите имя и фамилию.")
            return
        data = await state.get_data()
        raw_rating = data.get("rating")
        if not isinstance(raw_rating, int):
            await state.clear()
            await message.answer("Регистрация прервана. Нажмите кнопку «Регистрация» снова.")
            return
        try:
            player = registration_service.register(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=full_name,
                rating=raw_rating,
            )
        except DomainError as exc:
            await message.answer(f"Ошибка регистрации: {exc}")
            return

        await state.clear()
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

        group_order = ["Общие", "Игрок", "Тикеты", "Арбитраж", "Участники", "Столы", "Турнир", "Прочее"]
        order_index = {name: index for index, name in enumerate(group_order)}
        grouped: dict[str, list[CommandSpec]] = defaultdict(list)
        for spec in sorted(
            view.commands,
            key=lambda item: (order_index.get(item.group, len(group_order)), item.group, item.name),
        ):
            grouped[spec.group].append(spec)

        lines = ["Доступные команды:"]
        known_groups = [name for name in group_order if grouped.get(name)]
        extra_groups = sorted(name for name in grouped if name not in order_index)
        for group_name in [*known_groups, *extra_groups]:
            lines.append(f"\n{group_name}:")
            for spec in grouped[group_name]:
                lines.append(f"{spec.name} - {spec.description}")
        await message.answer("\n".join(lines))

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
        tournament = tournament_service.ensure_tournament()
        if tournament.status not in {TournamentStatus.ONGOING, TournamentStatus.FINISHED}:
            raise DomainError("Таблица лидеров будет доступна после старта турнира.")
        parts = (message.text or "").split()
        try:
            top_n = default_top if len(parts) < 2 else int(parts[1])
        except ValueError as exc:
            raise DomainError("Формат: /standings [top_n]") from exc
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
        parts = (message.text or "").split()
        if len(parts) != 1:
            raise DomainError("Формат: /close_ticket")
        closed = ticket_service.close_ticket(actor_id=message.from_user.id, ticket_id=None)
        await message.answer(f"Тикет #{closed.id} закрыт.")

    @router.message(Command("close_ticket_by_id"))
    async def close_ticket_by_id_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/close_ticket_by_id")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise DomainError("Формат: /close_ticket_by_id <ticket_id>")
        try:
            ticket_id = int(parts[1])
        except ValueError as exc:
            raise DomainError("ticket_id должен быть числом.") from exc
        closed = ticket_service.close_ticket(
            actor_id=message.from_user.id,
            ticket_id=ticket_id,
            audit_command="/close_ticket_by_id",
        )
        await message.answer(f"Тикет #{closed.id} закрыт.")

    @router.message(Command("create_ticket"))
    async def create_ticket_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/create_ticket")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2:
            raise DomainError("Формат: /create_ticket <arbitr|organizer> <описание>")
        try:
            ticket_type = TicketType(parts[1].strip().lower())
        except ValueError as exc:
            raise DomainError("Тип тикета должен быть arbitr или organizer.") from exc
        description = parts[2] if len(parts) > 2 else "Без описания"
        ticket = ticket_service.create_ticket(
            actor_id=message.from_user.id,
            ticket_type=ticket_type,
            description=description,
        )
        assignee_text = str(ticket.assignee_telegram_id) if ticket.assignee_telegram_id is not None else "не назначен"
        delivery_note = ""
        if ticket.assignee_telegram_id is not None:
            author_player = player_repo.get_by_telegram_id(message.from_user.id)
            author_table = (
                str(author_player.current_board)
                if author_player is not None and author_player.current_board is not None
                else "неизвестно"
            )
            delivered = await notify_user(
                message.bot,
                ticket.assignee_telegram_id,
                (
                    f"Новый тикет #{ticket.id}\n"
                    f"Тип: {ticket.ticket_type.value}\n"
                    f"Автор: {ticket.author_telegram_id}\n"
                    f"Стол отправителя: {author_table}\n"
                    f"Описание: {ticket.description}"
                ),
            )
            if not delivered:
                delivery_note = " Уведомление назначенному не доставлено."
        await message.answer(f"Тикет #{ticket.id} создан. Исполнитель: {assignee_text}.{delivery_note}")

    @router.message(Command("report"))
    async def report_handler(message: Message) -> None:
        if message.from_user is None:
            return
        acl.require(message.from_user.id, "/report")
        result_service.ensure_reportable_game(message.from_user.id)
        await message.answer("Выберите результат партии:", reply_markup=report_keyboard())

    @router.callback_query(F.data.startswith("report:"))
    async def report_callback_handler(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            return
        acl.require(callback.from_user.id, "/report")
        token = (callback.data or "").split(":", maxsplit=1)[1]
        chosen = scoring_service.parse_result_token(token)
        outcome = result_service.submit_player_report(callback.from_user.id, token)
        audit_logger.log_event(
            actor_id=callback.from_user.id,
            roles=[role.value for role in acl.resolve_roles(callback.from_user.id)],
            command="/report",
            entity=f"game:{outcome.game_id}",
            before=None,
            after={"status": outcome.status, "result": chosen.value},
            result="ok",
            reason=None,
        )
        if callback.message is not None:
            extra_hint = ""
            if outcome.status == "agreed" and outcome.next_round_hint:
                extra_hint = f"\n{outcome.next_round_hint}"
            await callback.message.answer(
                f"Вы выбрали: {chosen.value}\nИгра {outcome.game_id}: {outcome.message}{extra_hint}"
            )
            await _notify_report_peers(callback, outcome)
            if outcome.status == "agreed" and outcome.round_closed:
                await notify_admins_round_ready(callback.message.bot, outcome.round_number)
        await callback.answer()

    async def _notify_report_peers(callback: CallbackQuery, outcome: object) -> None:
        if callback.message is None:
            return
        bot = callback.message.bot
        actor_id = callback.from_user.id
        if not hasattr(outcome, "status"):
            return
        status = getattr(outcome, "status")
        if not isinstance(status, str):
            return

        if status == "pending":
            return

        white_telegram_id = getattr(outcome, "white_telegram_id", None)
        black_telegram_id = getattr(outcome, "black_telegram_id", None)
        confirmed_result = getattr(outcome, "confirmed_result", None)
        next_round_hint = getattr(outcome, "next_round_hint", None)
        game_id = getattr(outcome, "game_id", None)
        message = getattr(outcome, "message", None)

        if not isinstance(game_id, int) or not isinstance(message, str):
            return

        if status == "conflict":
            text = f"Игра {game_id}: {message}"
            for target in (white_telegram_id, black_telegram_id):
                if isinstance(target, int) and target != actor_id:
                    await notify_user(bot, target, text)
            return

        if status == "agreed":
            result_text = confirmed_result if isinstance(confirmed_result, str) else "результат подтвержден"
            schedule_hint = next_round_hint if isinstance(next_round_hint, str) else "Время следующего тура пока не назначено."
            text = f"Игра {game_id}: подтвержден результат {result_text}. {schedule_hint}"
            for target in (white_telegram_id, black_telegram_id):
                if isinstance(target, int) and target != actor_id:
                    await notify_user(bot, target, text)

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
        if current is not None:
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
            await message.answer(
                (
                    f"Тур {round_.number}, стол {current.board_number}, "
                    f"цвет {'White' if is_white else 'Black'}, "
                    f"соперник {opponent_name}, локация: {location}"
                )
            )
            return

        preview = _prepared_preview_for_player(player.id)
        if preview is None:
            await message.answer("Следующая партия пока не назначена.")
            return
        await message.answer(preview)

    def _prepared_preview_for_player(player_id: int) -> str | None:
        tournament = tournament_service.ensure_tournament()
        if tournament.status != TournamentStatus.REGISTRATION or not tournament.prepared:
            return None
        if tournament.current_round != 0 or not tournament.pending_pairing_payload:
            return None
        raw_payload = json.loads(tournament.pending_pairing_payload)
        if not isinstance(raw_payload, dict):
            return None
        bye_player_id = raw_payload.get("bye_player_id")
        if isinstance(bye_player_id, int) and bye_player_id == player_id:
            return "Предварительная информация: в первом туре у вас bye (1 очко)."

        games = raw_payload.get("games", [])
        if not isinstance(games, list):
            return None
        for item in games:
            if not isinstance(item, dict):
                continue
            white_player_id = item.get("white_player_id")
            black_player_id = item.get("black_player_id")
            if not isinstance(white_player_id, int) or not isinstance(black_player_id, int):
                continue
            if white_player_id != player_id and black_player_id != player_id:
                continue
            is_white = white_player_id == player_id
            opponent_id = black_player_id if is_white else white_player_id
            opponent = player_repo.get_by_id(opponent_id)
            location = str(item.get("location", "неизвестно"))
            raw_board_number = item.get("table_number")
            board_number = raw_board_number if isinstance(raw_board_number, int) else 0
            opponent_name = opponent.full_name if opponent is not None else f"id={opponent_id}"
            return (
                f"Предварительная информация тура 1: стол {board_number}, "
                f"цвет {'White' if is_white else 'Black'}, "
                f"соперник {opponent_name}, локация: {location}"
            )
        return None

    return router





