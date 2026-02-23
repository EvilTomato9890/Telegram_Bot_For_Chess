"""Organizer command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from domain.models import Table


def build_organizer_router(context: dict[str, object]) -> Router:
    """Create organizer router with tournament admin commands."""

    router = Router(name="organizer")
    acl = context["acl_service"]
    registration_service = context["registration_service"]
    tournament_service = context["tournament_service"]
    table_repo = context["table_repo"]
    player_repo = context["player_repo"]
    round_repo = context["round_repo"]
    game_repo = context["game_repo"]
    pairing_service = context["pairing_service"]
    scoring_service = context["scoring_service"]
    undo_service = context["undo_service"]
    notification_service = context["notification_service"]
    audit_logger = context["audit_logger"]

    def organizer_check(message: Message, command: str) -> int:
        if message.from_user is None:
            raise ValueError("Не удалось определить пользователя.")
        acl.require(message.from_user.id, command)
        return message.from_user.id

    def log_ok(actor: int, command: str, entity: str, after: dict[str, object], before: dict[str, object] | None = None) -> None:
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

    @router.message(Command("add_player"))
    async def add_player_handler(message: Message) -> None:
        actor = organizer_check(message, "/add_player")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: /add_player <telegram_id|@username> <имя>")
            return
        undo_service.snapshot(actor, "/add_player")
        raw_id = parts[1]
        full_name = parts[2].strip()
        if raw_id.startswith("@"):
            telegram_id = actor
            username = raw_id[1:]
        else:
            telegram_id = int(raw_id)
            username = None
        player = registration_service.add_player_by_organizer(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            rating=0,
        )
        log_ok(actor, "/add_player", f"player:{player.id}", {"telegram_id": player.telegram_id})
        await message.answer(f"Игрок добавлен: #{player.id} {player.full_name}.")

    @router.message(Command("disqualify"))
    async def disqualify_handler(message: Message) -> None:
        actor = organizer_check(message, "/disqualify")
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Формат: /disqualify <player_id>")
            return
        undo_service.snapshot(actor, "/disqualify")
        updated = registration_service.disqualify(int(parts[1]))
        log_ok(actor, "/disqualify", f"player:{updated.id}", {"status": updated.status.value})
        await message.answer(f"Игрок {updated.full_name} дисквалифицирован.")

    @router.message(Command("tables"))
    async def tables_handler(message: Message) -> None:
        organizer_check(message, "/tables")
        tables = table_repo.list_all()
        if not tables:
            await message.answer("Столы не добавлены.")
            return
        lines = [f"Стол {table.number}: {table.location} ({table.place_hint or 'без описания'})" for table in tables]
        await message.answer("\n".join(lines))

    @router.message(Command("add_table"))
    async def add_table_handler(message: Message) -> None:
        actor = organizer_check(message, "/add_table")
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: /add_table <номер> <локация>")
            return
        undo_service.snapshot(actor, "/add_table")
        number = int(parts[1])
        location = parts[2]
        table_repo.add(Table(id=None, number=number, location=location, place_hint=None))
        log_ok(actor, "/add_table", f"table:{number}", {"location": location})
        await message.answer(f"Стол {number} добавлен.")

    @router.message(Command("remove_table"))
    async def remove_table_handler(message: Message) -> None:
        actor = organizer_check(message, "/remove_table")
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Формат: /remove_table <номер>")
            return
        number = int(parts[1])
        current_round = round_repo.get_current()
        if current_round and current_round.id:
            for game in game_repo.list_by_round(current_round.id):
                if game.board_number == number and game.result is None:
                    await message.answer("Нельзя удалить стол: он используется в текущем туре.")
                    return
        undo_service.snapshot(actor, "/remove_table")
        removed = table_repo.remove_by_number(number)
        if not removed:
            await message.answer("Стол не найден.")
            return
        log_ok(actor, "/remove_table", f"table:{number}", {"removed": True})
        await message.answer(f"Стол {number} удален.")

    @router.message(Command("set_rules"))
    async def set_rules_handler(message: Message) -> None:
        actor = organizer_check(message, "/set_rules")
        text = (message.text or "").removeprefix("/set_rules").strip()
        if not text:
            await message.answer("Формат: /set_rules <текст>")
            return
        undo_service.snapshot(actor, "/set_rules")
        tournament_service.set_rules(text)
        log_ok(actor, "/set_rules", "tournament:1", {"rules_updated": True})
        await message.answer("Правила обновлены.")

    @router.message(Command("create_tournament"))
    async def create_tournament_handler(message: Message) -> None:
        actor = organizer_check(message, "/create_tournament")
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Формат: /create_tournament <число_столов>")
            return
        undo_service.snapshot(actor, "/create_tournament")
        tournament = tournament_service.create_tournament(int(parts[1]))
        log_ok(actor, "/create_tournament", "tournament:1", {"status": tournament.status.value})
        await message.answer(f"Турнир создан в статусе {tournament.status.value}.")

    @router.message(Command("open_registration"))
    async def open_registration_handler(message: Message) -> None:
        actor = organizer_check(message, "/open_registration")
        undo_service.snapshot(actor, "/open_registration")
        tournament = tournament_service.open_registration()
        log_ok(actor, "/open_registration", "tournament:1", {"status": tournament.status.value})
        await message.answer(f"Регистрация открыта. Статус: {tournament.status.value}.")

    @router.message(Command("set_round_number"))
    async def set_round_number_handler(message: Message) -> None:
        actor = organizer_check(message, "/set_round_number")
        parts = (message.text or "").split()
        if len(parts) < 2:
            await message.answer("Формат: /set_round_number <n> [confirm]")
            return
        rounds = int(parts[1])
        confirm = len(parts) > 2 and parts[2].lower() == "confirm"
        undo_service.snapshot(actor, "/set_round_number")
        tournament, recommendation = tournament_service.set_round_number(rounds, confirm=confirm)
        log_ok(actor, "/set_round_number", "tournament:1", {"number_of_rounds": tournament.number_of_rounds})
        await message.answer(
            f"Число туров установлено: {tournament.number_of_rounds}. Рекомендация системы: {recommendation}."
        )

    @router.message(Command("prepare_turnament"))
    async def prepare_tournament_handler(message: Message) -> None:
        actor = organizer_check(message, "/prepare_turnament")
        undo_service.snapshot(actor, "/prepare_turnament")
        tournament_service.prepare_tournament()
        players = sorted(player_repo.list_all(), key=lambda player: (-player.rating, player.id or 0))
        tables = table_repo.list_all()
        if tables:
            for index, player in enumerate(players, start=1):
                table = tables[(index - 1) % len(tables)]
                player.current_board = table.number
                player.seat_hint = f"Стол {table.number}, место {index}"
                player_repo.update(player)
        log_ok(actor, "/prepare_turnament", "tournament:1", {"prepared": True})
        await message.answer("Подготовка завершена. Регистрация закрыта для новых участников.")

    @router.message(Command("start_tournament"))
    async def start_tournament_handler(message: Message) -> None:
        actor = organizer_check(message, "/start_tournament")
        undo_service.snapshot(actor, "/start_tournament")
        tournament_service.start_tournament()
        outcome = pairing_service.generate_next_round(1, actor, force=False)
        if outcome.needs_confirmation:
            log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "needs_confirmation": True})
            await message.answer(
                f"Требуется подтверждение генерации тура: {outcome.confirmation_reason}\nИспользуйте /confirm_next_round."
            )
        else:
            log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "round": outcome.round_number})
            await message.answer(f"Турнир начат. Сгенерирован тур {outcome.round_number}.")
            for game in outcome.games:
                await message.answer(
                    f"Тур {outcome.round_number}: стол {game.board_number} - {game.white_player_id} vs {game.black_player_id}"
                )

    @router.message(Command("tournament_statuc"))
    async def tournament_status_handler(message: Message) -> None:
        organizer_check(message, "/tournament_statuc")
        summary = tournament_service.status_summary()
        await message.answer(
            "Состояние турнира:\n"
            f"status={summary['status']}\n"
            f"round={summary['round_current']}/{summary['rounds_total']}\n"
            f"prepared={summary['prepared']}\n"
            f"tables={summary['tables_count']}\n"
            f"active_players={summary['players_active']}\n"
            f"tables_enough={summary['enough_tables_for_next_round']}"
        )

    @router.message(Command("end_round"))
    async def end_round_handler(message: Message) -> None:
        actor = organizer_check(message, "/end_round")
        undo_service.snapshot(actor, "/end_round")
        tournament_service.end_current_round()
        log_ok(actor, "/end_round", "round:current", {"closed": True})
        await message.answer("Текущий тур закрыт.")

    @router.message(Command("next_round"))
    async def next_round_handler(message: Message) -> None:
        actor = organizer_check(message, "/next_round")
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
        await message.answer(f"Тур {outcome.round_number} начат.")
        for game in outcome.games:
            await message.answer(
                f"Тур {outcome.round_number}: стол {game.board_number} - {game.white_player_id} vs {game.black_player_id}"
            )

    @router.message(Command("confirm_next_round"))
    async def confirm_next_round_handler(message: Message) -> None:
        actor = organizer_check(message, "/confirm_next_round")
        undo_service.snapshot(actor, "/confirm_next_round")
        outcome = pairing_service.confirm_next_round(1, actor)
        log_ok(actor, "/confirm_next_round", f"round:{outcome.round_number}", {"forced": True})
        await message.answer(f"Тур {outcome.round_number} сгенерирован по подтверждению.")
        for game in outcome.games:
            await message.answer(
                f"Тур {outcome.round_number}: стол {game.board_number} - {game.white_player_id} vs {game.black_player_id}"
            )

    @router.message(Command("round"))
    async def round_handler(message: Message) -> None:
        organizer_check(message, "/round")
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Формат: /round <n>")
            return
        round_number = int(parts[1])
        round_ = round_repo.get_by_number(round_number)
        if round_ is None or round_.id is None:
            await message.answer("Тур не найден.")
            return
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
        actor = organizer_check(message, "/finish_tournament")
        undo_service.snapshot(actor, "/finish_tournament")
        tournament_service.finish_tournament()
        log_ok(actor, "/finish_tournament", "tournament:1", {"status": "finished"})
        standings = scoring_service.recalculate()
        top_lines = [f"{row.position}. {row.full_name} - {row.score}" for row in standings]
        await message.answer("Турнир завершен.\n" + "\n".join(top_lines))

    @router.message(Command("undo_last_action"))
    async def undo_last_action_handler(message: Message) -> None:
        actor = organizer_check(message, "/undo_last_action")
        undo_service.undo_last_organizer_action(actor)
        log_ok(actor, "/undo_last_action", "undo:last", {"restored": True})
        await message.answer("Последнее действие организатора отменено.")

    @router.message(Command("set_player_rating"))
    async def set_player_rating_handler(message: Message) -> None:
        actor = organizer_check(message, "/set_player_rating")
        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.answer("Формат: /set_player_rating <player_id> <rating>")
            return
        undo_service.snapshot(actor, "/set_player_rating")
        player = registration_service.set_rating(int(parts[1]), int(parts[2]))
        log_ok(actor, "/set_player_rating", f"player:{player.id}", {"rating": player.rating})
        await message.answer(f"Новый рейтинг игрока {player.full_name}: {player.rating}")

    return router
