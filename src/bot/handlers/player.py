"""Handlers for player-facing commands."""

from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.db.models import Game, Player, Round, Table, Tournament
from bot.domain.enums import GameResult, GameStatus, PlayerStatus, TournamentStatus
from bot.keyboards.common import main_menu_keyboard
from bot.utils.formatting import format_points, format_round_game

router = Router(name="player")

_STANDINGS_TOP_N = 10
_RESULT_MAP = {
    "1-0": GameResult.WHITE_WIN,
    "0-1": GameResult.BLACK_WIN,
    "0.5-0.5": GameResult.DRAW,
    "1/2-1/2": GameResult.DRAW,
}


class PlayerRegistration(StatesGroup):
    waiting_for_name = State()


def _normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    username = value.strip().lstrip("@").lower()
    return username or None


async def _get_current_tournament(session: AsyncSession) -> Tournament | None:
    result = await session.execute(
        select(Tournament)
        .where(Tournament.status.in_([TournamentStatus.ACTIVE, TournamentStatus.DRAFT]))
        .order_by(Tournament.id.desc())
    )
    return result.scalars().first()


async def _get_player(session: AsyncSession, tournament_id: int, telegram_id: int) -> Player | None:
    result = await session.execute(
        select(Player).where(Player.tournament_id == tournament_id, Player.telegram_id == telegram_id)
    )
    return result.scalars().first()


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "не задано"
    return value.strftime("%d.%m %H:%M")


async def _send_tournament_current(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Турнир пока не создан.")
            return

        result = await session.execute(
            select(Round).where(Round.tournament_id == tournament.id).order_by(Round.number.asc())
        )
        rounds = list(result.scalars().all())

    if not rounds:
        await message.answer("Расписание туров пока не сформировано.")
        return

    lines = ["🗓 Расписание туров:"]
    for round_item in rounds:
        lines.append(
            f"• Тур {round_item.number}: {_format_datetime(round_item.starts_at)} — {_format_datetime(round_item.ends_at)}"
        )
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def start_player(message: Message) -> None:
    """Greet regular users and show available player actions."""
    await message.answer(
        "Добро пожаловать в турнирного бота! Выберите действие в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("rules"))
async def player_rules(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        tournament = await _get_current_tournament(session)

    if tournament is None:
        await message.answer("Турнир пока не создан.")
        return

    if not tournament.rules_text.strip():
        await message.answer("Регламент пока не задан организатором.")
        return

    await message.answer(f"📜 Правила турнира:\n\n{tournament.rules_text}")


@router.message(Command("my_next"))
async def player_next_game(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Активного турнира пока нет.")
            return

        player = await _get_player(session, tournament.id, user.id)
        if player is None:
            await message.answer("Вы не зарегистрированы в текущем турнире.")
            return

        result = await session.execute(
            select(Game)
            .join(Round, Round.id == Game.round_id)
            .options(
                selectinload(Game.table),
                selectinload(Game.round),
                selectinload(Game.white_player),
                selectinload(Game.black_player),
            )
            .where(
                and_(
                    Round.tournament_id == tournament.id,
                    or_(Game.white_player_id == player.id, Game.black_player_id == player.id),
                    Round.number >= tournament.current_round,
                    Game.status.in_([GameStatus.PENDING, GameStatus.IN_PROGRESS]),
                )
            )
            .order_by(Round.number.asc(), Game.board_no.asc())
        )
        game = result.scalars().first()

    if game is None:
        await message.answer("Для вас пока нет назначенных предстоящих партий.")
        return

    is_white = game.white_player_id == player.id
    opponent = game.black_player if is_white else game.white_player
    opponent_name = opponent.display_name if opponent is not None else "BYE"
    color = "White" if is_white else "Black"
    location = game.table.location if isinstance(game.table, Table) else None

    await message.answer(
        format_round_game(
            round_number=game.round.number,
            table_number=game.board_no,
            color=color,
            opponent=opponent_name,
            location=location,
            seat=game.seat,
        )
    )


@router.message(Command("schedule"))
async def player_schedule(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await _send_tournament_current(message, session_factory)


@router.callback_query(lambda callback: callback.data == "tournament:current")
async def player_tournament_current_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await callback.answer()
    message = callback.message
    if not isinstance(message, Message):
        return
    await _send_tournament_current(message, session_factory)


@router.callback_query(lambda callback: callback.data == "player:register")
async def player_register_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await callback.answer()
    message = callback.message
    if not isinstance(message, Message):
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)

    if tournament is None or tournament.status != TournamentStatus.ACTIVE:
        await state.clear()
        await message.answer("Регистрация недоступна: сейчас нет активного турнира.")
        return

    await state.set_state(PlayerRegistration.waiting_for_name)
    await message.answer("Введите ваше имя для регистрации в текущем турнире.")


@router.message(PlayerRegistration.waiting_for_name)
async def player_register_name(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    display_name = message.text.strip() if message.text is not None else ""
    if not display_name:
        await message.answer("Имя не должно быть пустым. Введите имя еще раз.")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None or tournament.status != TournamentStatus.ACTIVE:
            await state.clear()
            await message.answer("Регистрация недоступна: сейчас нет активного турнира.")
            return

        existing_player = await _get_player(session, tournament.id, user.id)
        if existing_player is not None:
            await state.clear()
            await message.answer("Вы уже зарегистрированы в текущем турнире.")
            return

        player = Player(
            tournament_id=tournament.id,
            telegram_id=user.id,
            username=_normalize_username(user.username),
            display_name=display_name,
            score=0.0,
            buchholz=0.0,
            sonneborn_berger=0.0,
            median_buchholz=0.0,
            status=PlayerStatus.REGISTERED,
        )
        session.add(player)
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Вы зарегистрированы как {display_name}.")


@router.message(Command("my_score"))
async def player_score(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Активного турнира пока нет.")
            return
        player = await _get_player(session, tournament.id, user.id)

    if player is None:
        await message.answer("Вы не зарегистрированы в текущем турнире.")
        return

    await message.answer(
        "\n".join(
            [
                f"Ваши очки: {format_points(player.score)}",
                f"Buchholz: {player.buchholz:.2f}",
                f"Sonneborn-Berger: {player.sonneborn_berger:.2f}",
                f"Median Buchholz: {player.median_buchholz:.2f}",
            ]
        )
    )


@router.message(Command("standings"))
async def player_standings(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Активного турнира пока нет.")
            return

        result = await session.execute(
            select(Player)
            .where(Player.tournament_id == tournament.id)
            .order_by(
                Player.score.desc(),
                Player.buchholz.desc(),
                Player.sonneborn_berger.desc(),
                Player.median_buchholz.desc(),
                Player.id.asc(),
            )
        )
        players = list(result.scalars().all())

    if not players:
        await message.answer("В турнире пока нет участников.")
        return

    lines = ["🏆 Текущая таблица:"]
    for index, standing_player in enumerate(players[:_STANDINGS_TOP_N], start=1):
        lines.append(f"{index}. {standing_player.display_name} — {format_points(standing_player.score)}")

    my_position = next((idx for idx, item in enumerate(players, start=1) if item.telegram_id == user.id), None)
    if my_position is not None and my_position > _STANDINGS_TOP_N:
        own = players[my_position - 1]
        lines.append("...")
        lines.append(f"Ваше место: {my_position}. {own.display_name} — {format_points(own.score)}")

    await message.answer("\n".join(lines))


@router.message(Command("report"))
async def player_report(
    message: Message,
    command: CommandObject,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    if command.args is None:
        await message.answer("Формат: /report <round> <result>, где result: 1-0, 0-1, 0.5-0.5")
        return

    parts = command.args.split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Формат: /report <round> <result>, где result: 1-0, 0-1, 0.5-0.5")
        return

    round_number = int(parts[0])
    normalized_result = _RESULT_MAP.get(parts[1].strip())
    if normalized_result is None:
        await message.answer("Неверный результат. Разрешено: 1-0, 0-1, 0.5-0.5")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Активного турнира пока нет.")
            return

        player = await _get_player(session, tournament.id, user.id)
        if player is None:
            await message.answer("Вы не зарегистрированы в текущем турнире.")
            return

        result = await session.execute(
            select(Game)
            .join(Round, Round.id == Game.round_id)
            .where(
                Round.tournament_id == tournament.id,
                Round.number == round_number,
                or_(Game.white_player_id == player.id, Game.black_player_id == player.id),
            )
        )
        game = result.scalars().first()

        if game is None:
            await message.answer("Не найдена ваша партия в указанном туре.")
            return

        if game.black_player_id is None:
            await message.answer("Это BYE-партия. Репорт результата не требуется.")
            return

        if game.status == GameStatus.FINISHED:
            await message.answer("Результат этой партии уже утвержден и не может быть изменен.")
            return

        if game.reported_by is None:
            game.reported_by = player.id
            game.result = normalized_result
            game.requires_approval = True
            game.status = GameStatus.PENDING
            await session.commit()
            await message.answer(
                "Результат сохранен как pending. Ожидаем подтверждение соперника или организатора."
            )
            return

        if game.reported_by == player.id:
            await message.answer("Вы уже отправляли результат этой партии. Ожидайте подтверждение.")
            return

        if game.result != normalized_result:
            await message.answer(
                "Результат соперника отличается от вашего. Партия отправлена на проверку организатору."
            )
            return

        game.status = GameStatus.FINISHED
        game.requires_approval = False
        await session.commit()
        await message.answer("Результат подтвержден обоими игроками и зафиксирован.")
