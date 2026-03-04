"""Admin handlers for tournament lifecycle and reporting."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from domain.dto import PairingOutcome
from domain.exceptions import DomainError, RoundsExhaustedError
from domain.models import PlayerStatus, TournamentStatus

from .organizer_shared import OrganizerShared


def register_tournament_handlers(router: Router, shared: OrganizerShared) -> None:
    """Register tournament-lifecycle handlers on the provided router."""

    @router.message(Command("set_rules"))
    async def set_rules_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/set_rules")
        text = (message.text or "").removeprefix("/set_rules").strip()
        if not text:
            raise DomainError("Формат: /set_rules <текст>")
        shared.tournament_service.set_rules(text)
        shared.log_ok(actor, "/set_rules", "tournament:1", {"rules_updated": True})
        await shared.notify_players(message, lambda _: f"Обновлены правила турнира:\n{text}")
        await message.answer("Правила обновлены.")

    @router.message(Command("create_tournament"))
    async def create_tournament_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/create_tournament")
        parts = (message.text or "").split()
        if len(parts) != 1:
            raise DomainError("Формат: /create_tournament")
        tournament = shared.tournament_service.create_tournament()
        shared.log_ok(actor, "/create_tournament", "tournament:1", {"status": tournament.status.value})
        await message.answer("Турнир создан в статусе draft. Добавьте столы через /add_table.")

    @router.message(Command("open_registration"))
    async def open_registration_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/open_registration")
        shared.tournament_service.validate_open_registration()
        tournament = shared.tournament_service.open_registration()
        shared.log_ok(actor, "/open_registration", "tournament:1", {"status": tournament.status.value})
        await message.answer(f"Регистрация открыта. Статус: {tournament.status.value}.")

    @router.message(Command("set_round_number"))
    async def set_round_number_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/set_round_number")
        parts = (message.text or "").split()
        if len(parts) < 2:
            raise DomainError("Формат: /set_round_number <n> [confirm]")
        rounds = shared.parse_int(parts[1], field="число туров")
        confirm = len(parts) > 2 and parts[2].lower() == "confirm"
        shared.tournament_service.validate_set_round_number(rounds, confirm=confirm)
        tournament, recommendation = shared.tournament_service.set_round_number(rounds, confirm=confirm)
        shared.log_ok(actor, "/set_round_number", "tournament:1", {"number_of_rounds": tournament.number_of_rounds})
        await message.answer(
            f"Число туров установлено: {tournament.number_of_rounds}. Рекомендация системы: {recommendation}."
        )

    @router.message(Command("prepare_tournament"))
    async def prepare_tournament_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/prepare_tournament")
        problems = shared.tournament_service.validate_prepare_readiness()
        if problems:
            raise DomainError("Подготовка невозможна:\n- " + "\n- ".join(problems))

        shared.tournament_service.prepare_tournament()
        preview = shared.pairing_service.prepare_next_round_preview(1, actor)
        shared.log_ok(
            actor,
            "/prepare_tournament",
            "tournament:1",
            {"prepared": True, "preview_games": len(preview.games), "needs_confirmation": preview.needs_confirmation},
        )
        preview_map = shared.preview_messages_by_player(preview.games, preview.bye_player_id)
        await shared.notify_players(
            message,
            lambda player: preview_map.get(
                player.id or 0,
                "Турнир скоро начнется. Информация о паре появится позже.",
            ),
            include_disqualified=False,
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
        actor = shared.admin_check(message, "/start_tournament")
        shared.tournament_service.validate_start_tournament()
        tournament = shared.tournament_service.ensure_tournament()
        if tournament.current_round > 0:
            round_ = shared.round_repo.get_by_number(tournament.current_round)
            if round_ is None or round_.id is None:
                raise DomainError("Не удалось найти уже сгенерированный тур для старта турнира.")
            games = tuple(shared.game_repo.list_by_round(round_.id))
            shared.tournament_service.start_tournament()
            shared.log_ok(
                actor,
                "/start_tournament",
                "tournament:1",
                {"status": "ongoing", "round": tournament.current_round, "resumed": True},
            )
            await shared.notify_players(
                message,
                lambda _: f"Турнир начался. Стартует тур {tournament.current_round}.",
                include_disqualified=False,
            )
            await message.answer("\n".join(shared.render_round_games(tournament.current_round, games)))
            return
        if not tournament.pending_pairing_payload:
            # Defensive preflight: ensure there is pending payload for first round.
            shared.pairing_service.prepare_next_round_preview(1, actor)

        outcome: PairingOutcome = shared.pairing_service.generate_next_round(
            1,
            actor,
            force=False,
            allow_prestart=True,
        )
        shared.tournament_service.start_tournament()
        if outcome.needs_confirmation:
            shared.log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "needs_confirmation": True})
            await message.answer(
                "Требуется подтверждение генерации тура: "
                f"{outcome.confirmation_reason}\nИспользуйте /confirm_next_round."
            )
            return

        shared.log_ok(actor, "/start_tournament", "tournament:1", {"status": "ongoing", "round": outcome.round_number})
        await shared.notify_players(
            message,
            lambda _: f"Турнир начался. Стартует тур {outcome.round_number}.",
            include_disqualified=False,
        )
        await message.answer("\n".join(shared.render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("tournament_status"))
    async def tournament_status_handler(message: Message) -> None:
        shared.admin_check(message, "/tournament_status")
        summary = shared.tournament_service.status_summary()
        tournament = shared.tournament_service.ensure_tournament()
        players = shared.player_repo.list_all()
        active_players = [player for player in players if player.status == PlayerStatus.ACTIVE]
        dq_players = [player for player in players if player.status == PlayerStatus.DISQUALIFIED]
        tables = shared.table_repo.list_all()

        lines: list[str] = [
            "Состояние турнира:",
            f"status={summary['status']}",
            f"round={summary['round_current']}/{summary['rounds_total']}",
            f"prepared={summary['prepared']}",
            f"tables={summary['tables_count']}",
            f"active_players={summary['players_active']}",
            f"disqualified_players={summary['players_disqualified']}",
            f"tables_enough={summary['enough_tables_for_next_round']}",
            "",
            "Активные участники:",
        ]

        if not active_players:
            lines.append("- нет")
        else:
            for player in active_players:
                lines.append(
                    f"- #{player.id} {player.full_name} | tg={player.telegram_id} | rating={player.rating} | score={player.score}"
                )

        lines.extend(["", "Дисквалифицированные участники:"])
        if not dq_players:
            lines.append("- нет")
        else:
            for player in dq_players:
                lines.append(
                    f"- #{player.id} {player.full_name} | tg={player.telegram_id} | rating={player.rating} | score={player.score}"
                )

        lines.extend(["", "Столы:"])
        if not tables:
            lines.append("- нет")
        else:
            for table in tables:
                lines.append(f"- {table.number}: {table.location}")

        lines.extend(["", "Текущее размещение:"])
        placements = [
            f"- {player.full_name}: {player.seat_hint}"
            for player in active_players
            if player.seat_hint is not None and player.seat_hint.strip()
        ]
        if placements:
            lines.extend(placements)
        else:
            lines.append("- нет данных")

        lines.extend(["", "Таблица лидеров:"])
        if tournament.status in {TournamentStatus.ONGOING, TournamentStatus.FINISHED}:
            standings = shared.scoring_service.recalculate()
            if standings:
                for row in standings:
                    lines.append(
                        f"- {row.position}. {row.full_name} | score={row.score} | BH={row.buchholz} | MBH={row.median_buchholz} | SB={row.sonneborn_berger}"
                    )
            else:
                lines.append("- нет данных")
        else:
            lines.append("- недоступна до старта турнира")

        await shared.send_long_message(message, "\n".join(lines))

    @router.message(Command("end_round"))
    async def end_round_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/end_round")
        if not shared.validate_end_round_precheck():
            await message.answer("Текущий тур уже закрыт.")
            return
        shared.tournament_service.end_current_round()
        shared.log_ok(actor, "/end_round", "round:current", {"closed": True})

        tournament = shared.tournament_service.ensure_tournament()
        if tournament.number_of_rounds > 0 and tournament.current_round >= tournament.number_of_rounds:
            await shared.notify_admins(message, "Все запланированные туры завершены. Можно выполнить /finish_tournament.")
            await message.answer("Текущий тур закрыт. Достигнуто заданное число туров.")
            return

        await shared.notify_players(
            message,
            lambda _: "Текущий тур завершен. Ожидайте начало следующего.",
            include_disqualified=False,
        )
        await message.answer("Текущий тур закрыт.")

    @router.message(Command("prepare_round"))
    async def prepare_round_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/prepare_round")
        try:
            outcome = shared.pairing_service.prepare_round(1, actor)
        except RoundsExhaustedError as exc:
            await shared.notify_admins(message, "Все запланированные туры завершены. Можно выполнить /finish_tournament.")
            raise DomainError("Туры завершены. Выполните /finish_tournament.") from exc

        shared.log_ok(
            actor,
            "/prepare_round",
            f"round:{outcome.round_number}",
            {"prepared": True, "games": len(outcome.games), "needs_confirmation": outcome.needs_confirmation},
        )
        preview_map = shared.preview_messages_by_player(
            outcome.games,
            outcome.bye_player_id,
            round_number=outcome.round_number,
            intro="Подготовка",
        )
        await shared.notify_players(
            message,
            lambda player: preview_map.get(
                player.id or 0,
                f"Подготовка тура {outcome.round_number}: ожидайте назначение.",
            ),
            include_disqualified=False,
        )
        response = f"Тур {outcome.round_number} подготовлен. Участникам отправлены новые места."
        if outcome.needs_confirmation:
            response += (
                f"\nБез повторов пары не собрать: {outcome.confirmation_reason}\n"
                "Для старта тура используйте /confirm_next_round."
            )
        else:
            response += "\nДля запуска тура выполните /next_round."
        await message.answer(response)

    @router.message(Command("next_round"))
    async def next_round_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/next_round")
        try:
            pending_reason = shared.pairing_service.peek_pending_confirmation_reason(1, actor)
        except RoundsExhaustedError as exc:
            await shared.notify_admins(message, "Все запланированные туры завершены. Можно выполнить /finish_tournament.")
            raise DomainError("Туры завершены. Выполните /finish_tournament.") from exc

        if pending_reason is not None:
            shared.log_ok(actor, "/next_round", "round:pending", {"needs_confirmation": True})
            await message.answer(
                f"Без повторов пары не собрать: {pending_reason}\nДля продолжения используйте /confirm_next_round."
            )
            return

        try:
            outcome = shared.pairing_service.generate_next_round(1, actor, force=False)
        except RoundsExhaustedError as exc:
            await shared.notify_admins(message, "Все запланированные туры завершены. Можно выполнить /finish_tournament.")
            raise DomainError("Туры завершены. Выполните /finish_tournament.") from exc

        if outcome.needs_confirmation:
            shared.log_ok(actor, "/next_round", "round:pending", {"needs_confirmation": True})
            await message.answer(
                f"Без повторов пары не собрать: {outcome.confirmation_reason}\n"
                "Для продолжения используйте /confirm_next_round."
            )
            return

        shared.log_ok(actor, "/next_round", f"round:{outcome.round_number}", {"started": True})
        await shared.notify_players(message, lambda _: f"Начался тур {outcome.round_number}.", include_disqualified=False)
        await message.answer("\n".join(shared.render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("confirm_next_round"))
    async def confirm_next_round_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/confirm_next_round")
        shared.pairing_service.validate_confirm_next_round(1, actor)
        outcome = shared.pairing_service.confirm_next_round(1, actor)
        shared.log_ok(actor, "/confirm_next_round", f"round:{outcome.round_number}", {"forced": True})
        await shared.notify_players(
            message,
            lambda _: f"Подтвержден старт тура {outcome.round_number}.",
            include_disqualified=False,
        )
        await message.answer("\n".join(shared.render_round_games(outcome.round_number, outcome.games)))

    @router.message(Command("round"))
    async def round_handler(message: Message) -> None:
        shared.admin_check(message, "/round")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise DomainError("Формат: /round <n>")
        round_number = shared.parse_int(parts[1], field="номер тура")
        round_ = shared.round_repo.get_by_number(round_number)
        if round_ is None or round_.id is None:
            raise DomainError("Тур не найден.")
        games = shared.game_repo.list_by_round(round_.id)
        if not games:
            await message.answer("Для этого тура нет партий.")
            return

        lines = []
        for game in games:
            white = shared.player_repo.get_by_id(game.white_player_id)
            black = shared.player_repo.get_by_id(game.black_player_id)
            result = game.result.value if game.result else "-"
            lines.append(
                f"Стол {game.board_number}: {white.full_name if white else game.white_player_id} vs "
                f"{black.full_name if black else game.black_player_id} -> {result}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("finish_tournament"))
    async def finish_tournament_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/finish_tournament")
        shared.tournament_service.validate_finish_tournament()
        shared.tournament_service.finish_tournament()
        shared.log_ok(actor, "/finish_tournament", "tournament:1", {"status": "finished"})
        standings = shared.scoring_service.recalculate()
        positions = {row.telegram_id: row.position for row in standings}
        await shared.notify_players(
            message,
            lambda player: f"Турнир завершен. Ваша итоговая позиция: {positions.get(player.telegram_id, '-')}",
        )
        top_lines = [f"{row.position}. {row.full_name} - {row.score}" for row in standings]
        await message.answer("Турнир завершен.\n" + "\n".join(top_lines))

