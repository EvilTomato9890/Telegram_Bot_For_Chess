"""Admin command handlers."""

from __future__ import annotations

from collections.abc import Callable

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import RouterContext
from domain.models import Game, Player, Table, TournamentStatus


def build_organizer_router(context: RouterContext) -> Router:
    """Create router with admin tournament commands."""

    router = Router(name="organizer")
    acl = context.acl_service
    registration_service = context.registration_service
    tournament_service = context.tournament_service
    table_repo = context.table_repo
    player_repo = context.player_repo
    round_repo = context.round_repo
    game_repo = context.game_repo
    pairing_service = context.pairing_service
    scoring_service = context.scoring_service
    undo_service = context.undo_service
    notification_service = context.notification_service
    audit_logger = context.audit_logger

    def admin_check(message: Message, command: str) -> int:
        if message.from_user is None:
            raise ValueError("Не удалось определить пользователя.")
        acl.require(message.from_user.id, command)
        return message.from_user.id

    def log_ok(
        actor: int,
        command: str,
        entity: str,
        after: dict[str, object],
        before: dict[str, object] | None = None,
    ) -> None:
        audit_logger.log_event(
            actor_id=actor,
            roles=[role.value for role in acl.resolve_roles(actor)],
            command=command,
            entity=entity,
            before=before,
            after=after,
            result="ok",
            reason=None,
        )

    async def notify_players(message: Message, text_builder: Callable[[Player], str]) -> None:
        """Notify every registered player; ignore delivery failures."""

        bot = message.bot
        for player in player_repo.list_all():
            text = text_builder(player)
            notification_service.notify(f"[TO:{player.telegram_id}] {text}")
            if bot is None:
                continue
            try:
                await bot.send_message(player.telegram_id, text)
            except Exception:  # noqa: BLE001
                continue

    def parse_int(raw: str, *, field: str) -> int:
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{field} должен быть числом.") from exc

    async def send_long_message(message: Message, text: str) -> None:
        """Send long text in chunks accepted by Telegram."""

        chunk_size = 3500
        if len(text) <= chunk_size:
            await message.answer(text)
            return
        start = 0
        while start < len(text):
            await message.answer(text[start : start + chunk_size])
            start += chunk_size

    def render_round_games(round_number: int, games: tuple[Game, ...]) -> list[str]:
        lines: list[str] = []
        for game in games:
            white = player_repo.get_by_id(game.white_player_id)
            black = player_repo.get_by_id(game.black_player_id)
            white_name = white.full_name if white is not None else str(game.white_player_id)
            black_name = black.full_name if black is not None else str(game.black_player_id)
            if game.is_bye:
                lines.append(f"Тур {round_number}: {white_name} получает bye (1 очко)")
            else:
                lines.append(f"Тур {round_number}: стол {game.board_number} - {white_name} vs {black_name}")
        return lines

    def preview_messages_by_player(preview_games: tuple[Game, ...], bye_player_id: int | None) -> dict[int, str]:
        messages: dict[int, str] = {}
        for game in preview_games:
            table = table_repo.get_by_number(game.board_number)
            location = table.location if table is not None else "неизвестно"
            white = player_repo.get_by_id(game.white_player_id)
            black = player_repo.get_by_id(game.black_player_id)
            white_name = white.full_name if white is not None else f"id={game.white_player_id}"
            black_name = black.full_name if black is not None else f"id={game.black_player_id}"
            messages[game.white_player_id] = (
                f"Предварительная информация: стол {game.board_number}, цвет White, "
                f"соперник {black_name}, локация: {location}"
            )
            messages[game.black_player_id] = (
                f"Предварительная информация: стол {game.board_number}, цвет Black, "
                f"соперник {white_name}, локация: {location}"
            )
        if bye_player_id is not None:
            messages[bye_player_id] = "Предварительная информация: в первом туре у вас bye (1 очко)."
        return messages

    @router.message(Command("add_player"))
    async def add_player_handler(message: Message) -> None:
        actor = admin_check(message, "/add_player")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Формат: /add_player <telegram_id|@username> <имя>")
        undo_service.snapshot(actor, "/add_player")

        raw_id = parts[1].strip()
        full_name = parts[2].strip()
        if raw_id.startswith("@"):
            username = raw_id[1:]
            candidate = next((item for item in player_repo.list_all() if item.username == username), None)
            if candidate is None:
                raise ValueError(
                    "Для @username нужен уже известный пользователь. "
                    "Иначе используйте numeric telegram_id."
                )
            telegram_id = candidate.telegram_id
        else:
            telegram_id = parse_int(raw_id, field="telegram_id")
            username = None

        player = registration_service.add_player_by_admin(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            rating=0,
        )
        log_ok(actor, "/add_player", f"player:{player.id}", {"telegram_id": player.telegram_id})
        await message.answer(f"Игрок добавлен: #{player.id} {player.full_name}.")

    @router.message(Command("disqualify"))
    async def disqualify_handler(message: Message) -> None:
        actor = admin_check(message, "/disqualify")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise ValueError("Формат: /disqualify <player_id>")
        undo_service.snapshot(actor, "/disqualify")
        updated = registration_service.disqualify(parse_int(parts[1], field="player_id"))
        log_ok(actor, "/disqualify", f"player:{updated.id}", {"status": updated.status.value})
        await message.answer(f"Игрок {updated.full_name} дисквалифицирован.")

    @router.message(Command("tables"))
    async def tables_handler(message: Message) -> None:
        admin_check(message, "/tables")
        tables = table_repo.list_all()
        if not tables:
            await message.answer("Столы не добавлены.")
            return
        lines = [f"Стол {table.number}: {table.location}" for table in tables]
        await message.answer("\n".join(lines))

    @router.message(Command("add_table"))
    async def add_table_handler(message: Message) -> None:
        actor = admin_check(message, "/add_table")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Формат: /add_table <номер> <локация>")
        undo_service.snapshot(actor, "/add_table")
        number = parse_int(parts[1], field="номер стола")
        location = parts[2].strip()
        if not location:
            raise ValueError("Локация стола не может быть пустой.")
        table_repo.add(Table(id=None, number=number, location=location, place_hint=None))
        log_ok(actor, "/add_table", f"table:{number}", {"location": location})
        await message.answer(f"Стол {number} добавлен.")

    @router.message(Command("remove_table"))
    async def remove_table_handler(message: Message) -> None:
        actor = admin_check(message, "/remove_table")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise ValueError("Формат: /remove_table <номер>")
        number = parse_int(parts[1], field="номер стола")
        current_round = round_repo.get_current()
        if current_round and current_round.id:
            for game in game_repo.list_by_round(current_round.id):
                if game.board_number == number:
                    raise ValueError("Нельзя удалить стол: он используется в текущем туре.")
        undo_service.snapshot(actor, "/remove_table")
        removed = table_repo.remove_by_number(number)
        if not removed:
            raise ValueError("Стол не найден.")
        log_ok(actor, "/remove_table", f"table:{number}", {"removed": True})
        await message.answer(f"Стол {number} удален.")

    @router.message(Command("set_rules"))
    async def set_rules_handler(message: Message) -> None:
        actor = admin_check(message, "/set_rules")
        text = (message.text or "").removeprefix("/set_rules").strip()
        if not text:
            raise ValueError("Формат: /set_rules <текст>")
        undo_service.snapshot(actor, "/set_rules")
        tournament_service.set_rules(text)
        log_ok(actor, "/set_rules", "tournament:1", {"rules_updated": True})
        await notify_players(message, lambda _: f"Обновлены правила турнира:\n{text}")
        await message.answer("Правила обновлены.")

    @router.message(Command("create_tournament"))
    async def create_tournament_handler(message: Message) -> None:
        actor = admin_check(message, "/create_tournament")
        parts = (message.text or "").split()
        if len(parts) != 1:
            raise ValueError("Формат: /create_tournament")
        undo_service.snapshot(actor, "/create_tournament")
        tournament = tournament_service.create_tournament()
        log_ok(actor, "/create_tournament", "tournament:1", {"status": tournament.status.value})
        await message.answer("Турнир создан в статусе draft. Добавьте столы через /add_table.")

    @router.message(Command("open_registration"))
    async def open_registration_handler(message: Message) -> None:
        actor = admin_check(message, "/open_registration")
        undo_service.snapshot(actor, "/open_registration")
        tournament = tournament_service.open_registration()
        log_ok(actor, "/open_registration", "tournament:1", {"status": tournament.status.value})
        await message.answer(f"Регистрация открыта. Статус: {tournament.status.value}.")

    @router.message(Command("set_round_number"))
    async def set_round_number_handler(message: Message) -> None:
        actor = admin_check(message, "/set_round_number")
        parts = (message.text or "").split()
        if len(parts) < 2:
            raise ValueError("Формат: /set_round_number <n> [confirm]")
        rounds = parse_int(parts[1], field="число туров")
        confirm = len(parts) > 2 and parts[2].lower() == "confirm"
        undo_service.snapshot(actor, "/set_round_number")
        tournament, recommendation = tournament_service.set_round_number(rounds, confirm=confirm)
        log_ok(actor, "/set_round_number", "tournament:1", {"number_of_rounds": tournament.number_of_rounds})
        await message.answer(
            f"Число туров установлено: {tournament.number_of_rounds}. Рекомендация системы: {recommendation}."
        )

    @router.message(Command("prepare_tournament"))
    async def prepare_tournament_handler(message: Message) -> None:
        actor = admin_check(message, "/prepare_tournament")
        undo_service.snapshot(actor, "/prepare_tournament")
        tournament_service.prepare_tournament()
        preview = pairing_service.prepare_next_round_preview(1, actor)
        log_ok(
            actor,
            "/prepare_tournament",
            "tournament:1",
            {"prepared": True, "preview_games": len(preview.games), "needs_confirmation": preview.needs_confirmation},
        )
        preview_map = preview_messages_by_player(preview.games, preview.bye_player_id)
        await notify_players(
            message,
            lambda player: preview_map.get(player.id or 0, "Турнир скоро начнется. Информация о паре появится позже."),
        )
        response = "Подготовка завершена. Регистрация закрыта для новых участников."
        if preview.needs_confirmation:
            response += (
                f"\nДля старта тура потребуется подтверждение: {preview.confirmation_reason}. "
                "После /start_tournament используйте /confirm_next_round."
            )
        await message.answer(response)

    @router.message(Command("start_tournament"))
    async def start_tournament_handler(message: Message) -> None:
        actor = admin_check(message, "/start_tournament")
        undo_service.snapshot(actor, "/start_tournament")
        tournament_service.start_tournament()
        outcome = pairing_service.generate_next_round(1, actor, force=False)
        if outcome.needs_confirmation:
            log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "needs_confirmation": True})
            await message.answer(
                "Требуется подтверждение генерации тура: "
                f"{outcome.confirmation_reason}\nИспользуйте /confirm_next_round."
            )
            return

        log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "round": outcome.round_number})
        await notify_players(message, lambda _: f"Турнир начался. Стартует тур {outcome.round_number}.")
        await message.answer("\n".join(render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("tournament_status"))
    async def tournament_status_handler(message: Message) -> None:
        admin_check(message, "/tournament_status")
        summary = tournament_service.status_summary()
        tournament = tournament_service.ensure_tournament()
        players = player_repo.list_all()
        tables = table_repo.list_all()

        lines: list[str] = []
        lines.append("Состояние турнира:")
        lines.append(f"status={summary['status']}")
        lines.append(f"round={summary['round_current']}/{summary['rounds_total']}")
        lines.append(f"prepared={summary['prepared']}")
        lines.append(f"tables={summary['tables_count']}")
        lines.append(f"active_players={summary['players_active']}")
        lines.append(f"tables_enough={summary['enough_tables_for_next_round']}")
        lines.append("")

        lines.append("Участники:")
        if not players:
            lines.append("- нет")
        else:
            for player in players:
                lines.append(
                    (
                        f"- #{player.id} {player.full_name} | tg={player.telegram_id} | "
                        f"rating={player.rating} | status={player.status.value} | score={player.score}"
                    )
                )
        lines.append("")

        lines.append("Столы:")
        if not tables:
            lines.append("- нет")
        else:
            for table in tables:
                lines.append(f"- {table.number}: {table.location}")
        lines.append("")

        lines.append("Текущее размещение:")
        placements = [
            f"- {player.full_name}: {player.seat_hint}"
            for player in players
            if player.seat_hint is not None and player.seat_hint.strip()
        ]
        if placements:
            lines.extend(placements)
        else:
            lines.append("- нет данных")
        lines.append("")

        lines.append("Таблица лидеров:")
        if tournament.status in {TournamentStatus.ONGOING, TournamentStatus.FINISHED}:
            standings = scoring_service.recalculate()
            if standings:
                for row in standings:
                    lines.append(
                        (
                            f"- {row.position}. {row.full_name} | score={row.score} | "
                            f"BH={row.buchholz} | MBH={row.median_buchholz} | SB={row.sonneborn_berger}"
                        )
                    )
            else:
                lines.append("- нет данных")
        else:
            lines.append("- недоступна до старта турнира")

        await send_long_message(message, "\n".join(lines))

    @router.message(Command("end_round"))
    async def end_round_handler(message: Message) -> None:
        actor = admin_check(message, "/end_round")
        undo_service.snapshot(actor, "/end_round")
        tournament_service.end_current_round()
        log_ok(actor, "/end_round", "round:current", {"closed": True})
        await notify_players(message, lambda _: "Текущий тур завершен. Ожидайте начало следующего.")
        await message.answer("Текущий тур закрыт.")

    @router.message(Command("next_round"))
    async def next_round_handler(message: Message) -> None:
        actor = admin_check(message, "/next_round")
        undo_service.snapshot(actor, "/next_round")
        outcome = pairing_service.generate_next_round(1, actor, force=False)
        if outcome.needs_confirmation:
            log_ok(actor, "/next_round", "round:pending", {"needs_confirmation": True})
            await message.answer(
                f"Без повторов пары не собрать: {outcome.confirmation_reason}\n"
                "Для продолжения используйте /confirm_next_round."
            )
            return
        log_ok(actor, "/next_round", f"round:{outcome.round_number}", {"started": True})
        await notify_players(message, lambda _: f"Начался тур {outcome.round_number}.")
        await message.answer("\n".join(render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("confirm_next_round"))
    async def confirm_next_round_handler(message: Message) -> None:
        actor = admin_check(message, "/confirm_next_round")
        undo_service.snapshot(actor, "/confirm_next_round")
        outcome = pairing_service.confirm_next_round(1, actor)
        log_ok(actor, "/confirm_next_round", f"round:{outcome.round_number}", {"forced": True})
        await notify_players(message, lambda _: f"Подтвержден старт тура {outcome.round_number}.")
        await message.answer("\n".join(render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("round"))
    async def round_handler(message: Message) -> None:
        admin_check(message, "/round")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise ValueError("Формат: /round <n>")
        round_number = parse_int(parts[1], field="номер тура")
        round_ = round_repo.get_by_number(round_number)
        if round_ is None or round_.id is None:
            raise ValueError("Тур не найден.")
        games = game_repo.list_by_round(round_.id)
        if not games:
            await message.answer("Для этого тура нет партий.")
            return
        lines = []
        for game in games:
            white = player_repo.get_by_id(game.white_player_id)
            black = player_repo.get_by_id(game.black_player_id)
            result = game.result.value if game.result else "-"
            lines.append(
                f"Стол {game.board_number}: {white.full_name if white else game.white_player_id} vs "
                f"{black.full_name if black else game.black_player_id} -> {result}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("finish_tournament"))
    async def finish_tournament_handler(message: Message) -> None:
        actor = admin_check(message, "/finish_tournament")
        undo_service.snapshot(actor, "/finish_tournament")
        tournament_service.finish_tournament()
        log_ok(actor, "/finish_tournament", "tournament:1", {"status": "finished"})
        standings = scoring_service.recalculate()
        positions = {row.telegram_id: row.position for row in standings}
        await notify_players(
            message,
            lambda player: f"Турнир завершен. Ваша итоговая позиция: {positions.get(player.telegram_id, '-')}",
        )
        top_lines = [f"{row.position}. {row.full_name} - {row.score}" for row in standings]
        await message.answer("Турнир завершен.\n" + "\n".join(top_lines))

    @router.message(Command("undo_last_action"))
    async def undo_last_action_handler(message: Message) -> None:
        actor = admin_check(message, "/undo_last_action")
        undone = undo_service.undo_last_admin_action(actor)
        log_ok(
            actor,
            "/undo_last_action",
            f"undo:{undone.snapshot_id}",
            {"restored": True, "undone_action": undone.undone_action},
        )
        await message.answer(f"Отменено действие: {undone.undone_action}.")

    @router.message(Command("set_player_rating"))
    async def set_player_rating_handler(message: Message) -> None:
        actor = admin_check(message, "/set_player_rating")
        parts = (message.text or "").split()
        if len(parts) != 3:
            raise ValueError("Формат: /set_player_rating <player_id> <rating>")
        undo_service.snapshot(actor, "/set_player_rating")
        player_id = parse_int(parts[1], field="player_id")
        rating = parse_int(parts[2], field="rating")
        player = registration_service.set_rating(player_id, rating)
        log_ok(actor, "/set_player_rating", f"player:{player.id}", {"rating": player.rating})
        await message.answer(f"Новый рейтинг игрока {player.full_name}: {player.rating}")

    return router

