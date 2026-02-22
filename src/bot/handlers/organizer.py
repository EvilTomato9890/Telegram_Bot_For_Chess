"""Handlers for organizer-only commands."""

from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.db.models import Game, Player, Round, Table, Tournament
from bot.domain.enums import GameResult, GameStatus, PlayerStatus, RoundStatus, TournamentStatus
from bot.domain.swiss import swiss_pairings
from bot.domain.tiebreaks import MatchRecord, calculate_buchholz, calculate_sonneborn_berger
from bot.domain.validators import InvariantViolationError, validate_can_finish_tournament, validate_can_generate_round
from bot.services.acl import AccessControlService
from bot.services.tournament import InsufficientTablesError, TournamentService
from bot.utils.formatting import format_points

router = Router(name="organizer")


def _format_result(result: GameResult | None) -> str:
    if result is None:
        return "-"
    if result == GameResult.DRAW:
        return "0.5-0.5"
    return result.value


async def _get_current_tournament(session: AsyncSession) -> Tournament | None:
    result = await session.execute(
        select(Tournament)
        .where(Tournament.status.in_([TournamentStatus.ACTIVE, TournamentStatus.DRAFT]))
        .order_by(Tournament.id.desc())
    )
    return result.scalars().first()


def _is_organizer(message: Message, acl: AccessControlService) -> bool:
    user = message.from_user
    return user is not None and acl.is_organizer(user.id)


def _normalize_username(value: str) -> str | None:
    username = value.strip().lstrip("@").lower()
    return username or None


async def _resolve_telegram_id(
    message: Message,
    identifier: str,
    session: AsyncSession,
) -> tuple[int | None, str | None]:
    token = identifier.strip()
    logger.trace("Resolving telegram_id from identifier='{}'", token)

    if token.isdigit():
        logger.trace("Identifier is numeric telegram_id={}", token)
        return int(token), None

    if not token.startswith("@"):
        return None, "Укажите telegram_id числом или @username."

    username = _normalize_username(token)
    if not username:
        return None, "Укажите telegram_id числом или @username."

    existing_result = await session.execute(
        select(Player)
        .where(func.lower(Player.username) == username)
        .order_by(Player.id.desc())
        .limit(1)
    )
    existing_player = existing_result.scalars().first()
    if existing_player is not None:
        logger.debug(
            "Resolved telegram_id={} from stored player username @{}",
            existing_player.telegram_id,
            username,
        )
        return int(existing_player.telegram_id), None

    bot = message.bot
    if bot is None:
        return None, "Не удалось определить telegram_id по username. Укажите числовой telegram_id."

    try:
        chat = await bot.get_chat(chat_id=f"@{username}")
    except Exception:
        logger.warning("Failed to resolve @{} via bot.get_chat", username)
        return None, "Не удалось определить telegram_id по username. Укажите числовой telegram_id."

    logger.debug("Resolved telegram_id={} from bot.get_chat for @{}", chat.id, username)
    return int(chat.id), None


async def _recalculate_scores_and_tiebreaks(session: AsyncSession, tournament_id: int) -> None:
    players_result = await session.execute(select(Player).where(Player.tournament_id == tournament_id))
    players = list(players_result.scalars().all())
    by_id = {player.id: player for player in players}

    for player in players:
        player.score = 0.0
        player.buchholz = 0.0
        player.sonneborn_berger = 0.0
        player.median_buchholz = 0.0

    games_result = await session.execute(
        select(Game)
        .join(Round, Round.id == Game.round_id)
        .where(Round.tournament_id == tournament_id, Game.status == GameStatus.FINISHED)
        .order_by(Round.number.asc(), Game.board_no.asc())
    )
    games = list(games_result.scalars().all())

    matches: list[MatchRecord] = []
    for game in games:
        white = by_id.get(game.white_player_id)
        if white is None:
            continue

        black = by_id.get(game.black_player_id) if game.black_player_id is not None else None

        if game.result == GameResult.WHITE_WIN or game.result == GameResult.BYE:
            white_score = 1.0
            black_score = 0.0
        elif game.result == GameResult.BLACK_WIN:
            white_score = 0.0
            black_score = 1.0
        elif game.result == GameResult.DRAW:
            white_score = 0.5
            black_score = 0.5
        else:
            continue

        white.score += white_score
        matches.append(MatchRecord(player_id=white.id, opponent_id=black.id if black else None, score=white_score))

        if black is not None:
            black.score += black_score
            matches.append(MatchRecord(player_id=black.id, opponent_id=white.id, score=black_score))

    points = {player.id: player.score for player in players}
    buchholz = calculate_buchholz(points, matches)
    sonneborn = calculate_sonneborn_berger(points, matches)

    for player in players:
        player.buchholz = float(buchholz.get(player.id, 0.0))
        player.sonneborn_berger = float(sonneborn.get(player.id, 0.0))

    await session.commit()


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
                "/set_rules <текст>",
                "/start_tournament <rounds_count>",
                "/next_round",
                "/round <n>",
                "/approve_result <game_id>",
                "/finish_tournament",
                "/clear_history confirm",
            ]
        )
    )


@router.message(Command("clear_history"))
async def clear_history(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Delete non-active tournaments with explicit confirmation argument."""
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None or command.args.strip().lower() != "confirm":
        await message.answer(
            "Команда удаляет историю турниров (все, кроме ACTIVE). "
            "Для подтверждения выполните: /clear_history confirm"
        )
        return

    async with session_factory() as session:
        active_result = await session.execute(select(Tournament).where(Tournament.status == TournamentStatus.ACTIVE))
        active_tournaments = list(active_result.scalars().all())
        if active_tournaments:
            await message.answer("Удаление запрещено: найден активный турнир. Сначала завершите его.")
            return

        delete_result = await session.execute(select(Tournament).where(Tournament.status != TournamentStatus.ACTIVE))
        tournaments_to_delete = list(delete_result.scalars().all())

        if not tournaments_to_delete:
            await message.answer("История пуста: турниров для удаления нет.")
            return

        deleted_count = len(tournaments_to_delete)
        for tournament in tournaments_to_delete:
            await session.delete(tournament)

        await session.commit()

    await message.answer(f"✅ Удалено турниров: {deleted_count}.")


@router.message(Command("add_player"))
async def add_player(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
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

    display_name = parts[1].strip()
    if not display_name:
        await message.answer("Имя участника не может быть пустым.")
        return
    username = _normalize_username(parts[0]) if parts[0].startswith("@") else None

    async with session_factory() as session:
        telegram_id, error_text = await _resolve_telegram_id(message, parts[0], session)
        if error_text is not None or telegram_id is None:
            await message.answer(error_text or "Не удалось определить telegram_id.")
            return

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
    session_factory: async_sessionmaker[AsyncSession],
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
            username = _normalize_username(target)
            if username is None:
                await message.answer("Укажите player_id числом или @username.")
                return
            player_query = player_query.where(func.lower(Player.username) == username)
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
async def list_tables(message: Message, acl: AccessControlService, session_factory: async_sessionmaker[AsyncSession]) -> None:
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
    session_factory: async_sessionmaker[AsyncSession],
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
    session_factory: async_sessionmaker[AsyncSession],
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


@router.message(Command("set_rules"))
async def set_rules(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    rules_text = (command.args or "").strip()
    if not rules_text:
        await message.answer("Формат: /set_rules <текст>")
        return

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Нет активного или чернового турнира.")
            return

        tournament.rules_text = rules_text
        await session.commit()

    await message.answer("✅ Регламент турнира обновлен.")


@router.message(Command("start_tournament"))
async def start_tournament(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None or not command.args.strip().isdigit():
        await message.answer("Формат: /start_tournament <rounds_count>")
        return

    rounds_count = int(command.args.strip())
    if rounds_count <= 0:
        await message.answer("Количество туров должно быть положительным числом.")
        return

    async with session_factory() as session:
        active_result = await session.execute(
            select(Tournament).where(Tournament.status == TournamentStatus.ACTIVE).order_by(Tournament.id.desc())
        )
        active_tournament = active_result.scalars().first()
        if active_tournament is not None:
            await message.answer("Уже есть активный турнир. Завершите его перед запуском нового.")
            return

        draft_result = await session.execute(
            select(Tournament).where(Tournament.status == TournamentStatus.DRAFT).order_by(Tournament.id.desc())
        )
        tournament = draft_result.scalars().first()
        if tournament is None:
            tournament = Tournament(rounds_count=rounds_count, status=TournamentStatus.ACTIVE)
            session.add(tournament)
        else:
            tournament.rounds_count = rounds_count
            tournament.status = TournamentStatus.ACTIVE

        await session.commit()
        await session.refresh(tournament)

    await message.answer(f"✅ Турнир #{tournament.id} запущен. Количество туров: {tournament.rounds_count}.")


@router.message(Command("next_round"))
async def next_round(message: Message, acl: AccessControlService, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    async with session_factory() as session:
        tournament_result = await session.execute(
            select(Tournament).where(Tournament.status == TournamentStatus.ACTIVE).order_by(Tournament.id.desc())
        )
        tournament = tournament_result.scalars().first()
        if tournament is None:
            await message.answer("Нет активного турнира. Используйте /start_tournament.")
            return

        if tournament.current_round >= tournament.rounds_count:
            await message.answer("Достигнуто максимальное число туров. Завершите турнир командой /finish_tournament.")
            return

        current_round = None
        if tournament.current_round > 0:
            current_round_result = await session.execute(
                select(Round).where(
                    Round.tournament_id == tournament.id,
                    Round.number == tournament.current_round,
                )
            )
            current_round = current_round_result.scalars().first()

        try:
            validate_can_generate_round(current_round_status=current_round.status if current_round else None)
        except InvariantViolationError:
            await message.answer("Нельзя генерировать следующий тур, пока текущий тур не закрыт.")
            return

        players_result = await session.execute(
            select(Player)
            .where(Player.tournament_id == tournament.id, Player.status != PlayerStatus.DISQUALIFIED)
            .order_by(
                Player.score.desc(),
                Player.buchholz.desc(),
                Player.sonneborn_berger.desc(),
                Player.id.asc(),
            )
        )
        players = list(players_result.scalars().all())
        if len(players) < 2:
            await message.answer("Недостаточно участников для генерации тура.")
            return

        history_result = await session.execute(
            select(Game.white_player_id, Game.black_player_id)
            .join(Round, Round.id == Game.round_id)
            .where(
                Round.tournament_id == tournament.id,
                Game.black_player_id.is_not(None),
            )
        )
        history = [(w, b) for w, b in history_result.all() if b is not None]

        pairings = swiss_pairings(
            [player.id for player in players],
            scores={player.id: player.score for player in players},
            history=history,
            color_history={player.id: player.color_history for player in players},
            had_bye={player.id for player in players if player.had_bye},
        )

        tables_result = await session.execute(select(Table).where(Table.is_active.is_(True)).order_by(Table.number.asc()))
        tables = list(tables_result.scalars().all())
        service = TournamentService(tournaments=None, players=None)
        try:
            assignments = service.assign_tables(pairings, tables)
        except InsufficientTablesError as exc:
            await message.answer(str(exc))
            return

        next_round_number = tournament.current_round + 1
        round_entity = Round(tournament_id=tournament.id, number=next_round_number, status=RoundStatus.ACTIVE)
        session.add(round_entity)
        await session.flush()

        assignment_by_pair = {(a.white_player_id, a.black_player_id): a for a in assignments}
        board_no_for_bye = len(assignments) + 1

        lines = [f"✅ Тур {next_round_number} сгенерирован:"]
        for white_id, black_id in pairings:
            if black_id is None:
                bye_game = Game(
                    round_id=round_entity.id,
                    board_no=board_no_for_bye,
                    white_player_id=white_id,
                    black_player_id=None,
                    result=GameResult.BYE,
                    status=GameStatus.FINISHED,
                    requires_approval=False,
                )
                session.add(bye_game)
                white_player = next(player for player in players if player.id == white_id)
                white_player.had_bye = True
                lines.append(f"• {white_player.display_name} — BYE")
                continue

            assignment = assignment_by_pair[(white_id, black_id)]
            game = Game(
                round_id=round_entity.id,
                board_no=assignment.board_no,
                table_id=assignment.table_id,
                white_player_id=white_id,
                black_player_id=black_id,
                status=GameStatus.PENDING,
                requires_approval=False,
            )
            session.add(game)

            white_player = next(player for player in players if player.id == white_id)
            black_player = next(player for player in players if player.id == black_id)
            white_player.color_history = f"{white_player.color_history}W"
            black_player.color_history = f"{black_player.color_history}B"

            table = next((item for item in tables if item.id == assignment.table_id), None)
            location = table.location if table is not None and table.location else "локация не указана"
            lines.append(
                f"• Стол {assignment.board_no}: {white_player.display_name} (White) vs "
                f"{black_player.display_name} (Black), {location}"
            )

        if current_round is not None and current_round.status != RoundStatus.FINISHED:
            current_round.status = RoundStatus.FINISHED

        tournament.current_round = next_round_number
        await session.commit()

        await _recalculate_scores_and_tiebreaks(session, tournament.id)

    await message.answer("\n".join(lines))


@router.message(Command("round"))
async def show_round(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None or not command.args.strip().isdigit():
        await message.answer("Формат: /round <n>")
        return

    round_number = int(command.args.strip())

    async with session_factory() as session:
        tournament = await _get_current_tournament(session)
        if tournament is None:
            await message.answer("Нет активного или чернового турнира.")
            return

        round_result = await session.execute(
            select(Round).where(Round.tournament_id == tournament.id, Round.number == round_number)
        )
        round_entity = round_result.scalars().first()
        if round_entity is None:
            await message.answer("Тур с таким номером не найден.")
            return

        games_result = await session.execute(
            select(Game)
            .options(selectinload(Game.white_player), selectinload(Game.black_player), selectinload(Game.table))
            .where(Game.round_id == round_entity.id)
            .order_by(Game.board_no.asc())
        )
        games = list(games_result.scalars().all())

    if not games:
        await message.answer(f"В туре {round_number} пока нет партий.")
        return

    lines = [f"📋 Тур {round_number} ({round_entity.status.value}):"]
    for game in games:
        white = game.white_player.display_name if game.white_player is not None else "-"
        if game.black_player_id is None:
            lines.append(f"• {white} — BYE ({_format_result(game.result)})")
            continue

        black = game.black_player.display_name if game.black_player is not None else "-"
        table_no = game.board_no
        location = game.table.location if game.table is not None and game.table.location else "локация не указана"
        lines.append(f"• Стол {table_no}: {white} vs {black} | результат: {_format_result(game.result)} | {location}")

    await message.answer("\n".join(lines))


@router.message(Command("approve_result"))
async def approve_result(
    message: Message,
    command: CommandObject,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    if command.args is None or not command.args.strip().isdigit():
        await message.answer("Формат: /approve_result <game_id>")
        return

    game_id = int(command.args.strip())

    async with session_factory() as session:
        result = await session.execute(
            select(Game)
            .options(selectinload(Game.round))
            .join(Round, Round.id == Game.round_id)
            .join(Tournament, Tournament.id == Round.tournament_id)
            .where(Game.id == game_id, Tournament.status.in_([TournamentStatus.ACTIVE, TournamentStatus.DRAFT]))
        )
        game = result.scalars().first()
        if game is None:
            await message.answer("Партия не найдена в текущем турнире.")
            return

        if game.black_player_id is None:
            await message.answer("BYE-партия не требует подтверждения.")
            return

        if game.result is None:
            await message.answer("У этой партии пока нет заявленного результата.")
            return

        if game.status == GameStatus.FINISHED and not game.requires_approval:
            await message.answer("Результат уже утвержден.")
            return

        game.status = GameStatus.FINISHED
        game.requires_approval = False

        round_games_result = await session.execute(select(Game).where(Game.round_id == game.round_id))
        round_games = list(round_games_result.scalars().all())
        if round_games and all(item.status == GameStatus.FINISHED for item in round_games):
            game.round.status = RoundStatus.FINISHED

        await session.commit()

        tournament_id = game.round.tournament_id
        await _recalculate_scores_and_tiebreaks(session, tournament_id)

    await message.answer("✅ Результат партии утвержден.")


@router.message(Command("finish_tournament"))
async def finish_tournament(
    message: Message,
    acl: AccessControlService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_organizer(message, acl):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    async with session_factory() as session:
        tournament_result = await session.execute(
            select(Tournament).where(Tournament.status == TournamentStatus.ACTIVE).order_by(Tournament.id.desc())
        )
        tournament = tournament_result.scalars().first()
        if tournament is None:
            await message.answer("Нет активного турнира для завершения.")
            return

        rounds_result = await session.execute(select(Round).where(Round.tournament_id == tournament.id))
        rounds = list(rounds_result.scalars().all())

        pending_games_result = await session.execute(
            select(Game)
            .join(Round, Round.id == Game.round_id)
            .where(
                Round.tournament_id == tournament.id,
                or_(Game.status != GameStatus.FINISHED, and_(Game.status == GameStatus.FINISHED, Game.result.is_(None))),
            )
        )
        has_pending_games = pending_games_result.scalars().first() is not None

        try:
            validate_can_finish_tournament(
                tournament_status=tournament.status,
                has_unfinished_rounds=any(item.status != RoundStatus.FINISHED for item in rounds),
                has_pending_games=has_pending_games,
            )
        except InvariantViolationError as exc:
            await message.answer(f"Нельзя завершить турнир: {exc}")
            return

        await _recalculate_scores_and_tiebreaks(session, tournament.id)

        tournament.status = TournamentStatus.FINISHED
        tournament.finished_at = datetime.utcnow()
        await session.commit()

        standings_result = await session.execute(
            select(Player)
            .where(Player.tournament_id == tournament.id)
            .order_by(
                Player.score.desc(),
                Player.buchholz.desc(),
                Player.sonneborn_berger.desc(),
                Player.id.asc(),
            )
        )
        standings = list(standings_result.scalars().all())

    lines = ["🏁 Турнир завершен. Итоговая таблица:"]
    for i, player in enumerate(standings[:10], start=1):
        lines.append(
            f"{i}. {player.display_name} — {format_points(player.score)} "
            f"(BH {player.buchholz:.2f}, SB {player.sonneborn_berger:.2f})"
        )
    await message.answer("\n".join(lines))
