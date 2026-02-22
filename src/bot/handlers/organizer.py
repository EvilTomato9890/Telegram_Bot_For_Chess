"""Handlers for organizer-only commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.models import Game, Player, Round, Table, Tournament
from bot.domain.enums import PlayerStatus, TournamentStatus
from bot.services.acl import AccessControlService

router = Router(name="organizer")


async def _get_current_tournament(session) -> Tournament | None:
    result = await session.execute(
        select(Tournament)
        .where(Tournament.status.in_([TournamentStatus.ACTIVE, TournamentStatus.DRAFT]))
        .order_by(Tournament.id.desc())
    )
    return result.scalars().first()


def _is_organizer(message: Message, acl: AccessControlService) -> bool:
    user = message.from_user
    return user is not None and acl.is_organizer(user.id)


async def _resolve_telegram_id(message: Message, identifier: str) -> tuple[int | None, str | None]:
    token = identifier.strip()
    if token.isdigit():
        return int(token), None

    if not token.startswith("@"):
        return None, "Укажите telegram_id числом или @username."

    username = token[1:]
    if not username:
        return None, "Укажите telegram_id числом или @username."

    try:
        chat = await message.bot.get_chat(chat_id=f"@{username}")
    except Exception:
        return None, "Не удалось определить telegram_id по username. Укажите числовой telegram_id."

    return int(chat.id), None


@router.message(Command("organizer"))
async def organizer_help(message: Message, acl: AccessControlService) -> None:
    """Show organizer panel command hints if the user has required rights."""
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    await message.answer(
        "\n".join(
            [
                "Команды организатора:",
                "/organizer",
                "/add_player <telegram_id|@username> <имя>",
                "/disqualify <player_id|@username>",
                "/tables",
                "/add_table <номер> <локация>",
                "/remove_table <номер>",
            ]
        )
    )


@router.message(Command("add_player"))
async def add_player(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker,
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None:
        await message.answer("Формат: /add_player <telegram_id|@username> <имя>")
        return

    parts = command.args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /add_player <telegram_id|@username> <имя>")
        return

    telegram_id, error_text = await _resolve_telegram_id(message, parts[0])
    if error_text is not None or telegram_id is None:
        await message.answer(error_text or "Не удалось определить telegram_id.")
        return

    display_name = parts[1].strip()
    if not display_name:
        await message.answer("Имя участника не может быть пустым.")
        return

    username = parts[0][1:] if parts[0].startswith("@") else None

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Нет активного или чернового турнира. Сначала создайте/запустите турнир.")
            return

        existing_result = await session.execute(
            select(Player).where(Player.tournament_id == tournament.id, Player.telegram_id == telegram_id)
        )
        if existing_result.scalars().first() is not None:
            await message.answer("Участник с таким telegram_id уже добавлен в текущий турнир.")
            return

        player = Player(
            tournament_id=tournament.id,
            telegram_id=telegram_id,
            username=username,
            display_name=display_name,
            status=PlayerStatus.REGISTERED,
        )
        session.add(player)
        await session.commit()
        await session.refresh(player)

    await message.answer(
        f"✅ Участник добавлен: {player.display_name} (player_id={player.id}, telegram_id={player.telegram_id})."
    )


@router.message(Command("disqualify"))
async def disqualify_player(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker,
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None:
        await message.answer("Формат: /disqualify <player_id|@username>")
        return

    target = command.args.strip()
    if not target:
        await message.answer("Формат: /disqualify <player_id|@username>")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Нет активного или чернового турнира.")
            return

        player_query = select(Player).where(Player.tournament_id == tournament.id)
        if target.isdigit():
            player_query = player_query.where(Player.id == int(target))
        elif target.startswith("@"):
            player_query = player_query.where(Player.username == target[1:])
        else:
            await message.answer("Укажите player_id числом или @username.")
            return

        result = await session.execute(player_query)
        player = result.scalars().first()
        if player is None:
            await message.answer("Участник не найден в текущем турнире.")
            return

        if player.status == PlayerStatus.DISQUALIFIED:
            await message.answer("Участник уже дисквалифицирован.")
            return

        player.status = PlayerStatus.DISQUALIFIED
        await session.commit()

    await message.answer(f"⛔ Участник {player.display_name} (player_id={player.id}) дисквалифицирован.")


@router.message(Command("tables"))
async def list_tables(message: Message, acl: AccessControlService, session_factory: async_sessionmaker) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    async with session_factory() as session:
        result = await session.execute(select(Table).order_by(Table.number.asc()))
        tables = list(result.scalars().all())

    if not tables:
        await message.answer("Столы пока не добавлены.")
        return

    lines = ["🪑 Список столов:"]
    for table in tables:
        location = table.location or "локация не указана"
        status = "активен" if table.is_active else "неактивен"
        lines.append(f"• Стол {table.number}: {location} ({status})")
    await message.answer("\n".join(lines))


@router.message(Command("add_table"))
async def add_table(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker,
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None:
        await message.answer("Формат: /add_table <номер> <локация>")
        return

    parts = command.args.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Формат: /add_table <номер> <локация>")
        return

    number = int(parts[0])
    location = parts[1].strip()
    if number <= 0:
        await message.answer("Номер стола должен быть положительным числом.")
        return

    if not location:
        await message.answer("Локация стола не может быть пустой.")
        return

    async with session_factory() as session:
        result = await session.execute(select(Table).where(Table.number == number))
        if result.scalars().first() is not None:
            await message.answer("Стол с таким номером уже существует.")
            return

        table = Table(number=number, location=location, is_active=True)
        session.add(table)
        await session.commit()

    await message.answer(f"✅ Добавлен стол {number}: {location}.")


@router.message(Command("remove_table"))
async def remove_table(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker,
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None or not command.args.strip().isdigit():
        await message.answer("Формат: /remove_table <номер>")
        return

    number = int(command.args.strip())

    async with session_factory() as session:
        table_result = await session.execute(select(Table).where(Table.number == number))
        table = table_result.scalars().first()
        if table is None:
            await message.answer("Стол с таким номером не найден.")
            return

        tournament = await _get_current_tournament(session)
        if tournament is not None and tournament.current_round > 0:
            game_result = await session.execute(
                select(Game)
                .join(Round, Round.id == Game.round_id)
                .where(
                    and_(
                        Round.tournament_id == tournament.id,
                        Round.number == tournament.current_round,
                        Game.table_id == table.id,
                    )
                )
            )
            if game_result.scalars().first() is not None:
                await message.answer("Нельзя удалить стол: он используется в текущем туре.")
                return

        await session.delete(table)
        await session.commit()

    await message.answer(f"🗑 Стол {number} удален.")
