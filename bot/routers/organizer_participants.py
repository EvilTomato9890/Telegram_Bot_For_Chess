"""Admin handlers for participant roster and announcements."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from domain.exceptions import DomainError
from domain.models import PlayerStatus, TournamentStatus

from .organizer_shared import OrganizerShared


def register_participant_handlers(router: Router, shared: OrganizerShared) -> None:
    """Register participant-management handlers on the provided router."""

    @router.message(Command("add_player"))
    async def add_player_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/add_player")
        pending_was_prepared = shared.tournament_service.ensure_tournament().pending_pairing_payload is not None
        shared.registration_service.validate_admin_add_precheck()
        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 4:
            raise DomainError("Формат: /add_player <telegram_id|@username> <rating> <имя>")

        raw_id = parts[1].strip()
        rating = shared.parse_int(parts[2], field="rating")
        if rating < 0:
            raise DomainError("Рейтинг не может быть отрицательным.")
        full_name = parts[3].strip()
        if not full_name:
            raise DomainError("Имя игрока не может быть пустым.")

        if raw_id.startswith("@"):
            username_token = raw_id[1:]
            telegram_id: int | None = None
            username: str | None = username_token
            if message.bot is not None:
                try:
                    chat = await message.bot.get_chat(raw_id)
                    if isinstance(chat.id, int) and chat.id > 0:
                        telegram_id = chat.id
                    if chat.username:
                        username = chat.username
                except Exception:  # noqa: BLE001
                    telegram_id = None
            if telegram_id is None:
                candidate = shared.player_repo.get_by_username(username_token)
                if candidate is not None:
                    telegram_id = candidate.telegram_id
                    username = candidate.username
            if telegram_id is None:
                raise DomainError(
                    "Не удалось определить telegram_id по @username. "
                    "Используйте numeric telegram_id или попросите пользователя написать боту /start."
                )
        else:
            telegram_id = shared.parse_int(raw_id, field="telegram_id")
            username = None

        if shared.player_repo.get_by_telegram_id(telegram_id) is not None:
            raise DomainError("Игрок с таким telegram_id уже существует.")

        player = shared.registration_service.add_player_by_admin(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            rating=rating,
        )
        shared.log_ok(actor, "/add_player", f"player:{player.id}", {"telegram_id": player.telegram_id, "rating": player.rating})
        response = f"Игрок добавлен: #{player.id} {player.full_name}, рейтинг {player.rating}."
        if pending_was_prepared:
            response += " Подготовленные пары сброшены, переподготовьте тур перед запуском."
        await message.answer(response)

    @router.message(Command("delete_player"))
    async def delete_player_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/delete_player")
        pending_was_prepared = shared.tournament_service.ensure_tournament().pending_pairing_payload is not None
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise DomainError("Формат: /delete_player <player_id>")
        player_id = shared.parse_int(parts[1], field="player_id")
        tournament = shared.tournament_service.ensure_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION} or tournament.prepared:
            raise DomainError("Удалять игрока можно только до старта турнира.")
        if shared.player_repo.get_by_id(player_id) is None:
            raise DomainError("Игрок не найден.")
        deleted = shared.registration_service.delete_player_by_admin(player_id)
        shared.log_ok(actor, "/delete_player", f"player:{player_id}", {"deleted": True, "full_name": deleted.full_name})
        response = f"Игрок удален: #{player_id} {deleted.full_name}."
        if pending_was_prepared:
            response += " Подготовленные пары сброшены, переподготовьте тур перед запуском."
        await message.answer(response)

    @router.message(Command("disqualify"))
    async def disqualify_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/disqualify")
        pending_was_prepared = shared.tournament_service.ensure_tournament().pending_pairing_payload is not None
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise DomainError("Формат: /disqualify <player_id>")
        player_id = shared.parse_int(parts[1], field="player_id")
        player = shared.player_repo.get_by_id(player_id)
        if player is None:
            raise DomainError("Игрок не найден.")
        if player.status == PlayerStatus.DISQUALIFIED:
            raise DomainError("Игрок уже дисквалифицирован.")
        updated = shared.registration_service.disqualify(player_id)
        shared.log_ok(actor, "/disqualify", f"player:{updated.id}", {"status": updated.status.value})
        response = f"Игрок {updated.full_name} дисквалифицирован."
        if pending_was_prepared:
            response += " Подготовленные пары сброшены, выполните /prepare_round."
        await message.answer(response)

    @router.message(Command("announce"))
    async def announce_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/announce")
        text = (message.text or "").removeprefix("/announce").strip()
        if not text:
            raise DomainError("Формат: /announce <текст>")
        await shared.notify_players(message, lambda _: f"Объявление от администратора:\n{text}")
        shared.log_ok(actor, "/announce", "players:all", {"announcement": text})
        await message.answer("Объявление отправлено всем участникам.")

    @router.message(Command("set_player_rating"))
    async def set_player_rating_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/set_player_rating")
        pending_was_prepared = shared.tournament_service.ensure_tournament().pending_pairing_payload is not None
        parts = (message.text or "").split()
        if len(parts) != 3:
            raise DomainError("Формат: /set_player_rating <player_id> <rating>")
        player_id = shared.parse_int(parts[1], field="player_id")
        rating = shared.parse_int(parts[2], field="rating")
        if rating < 0:
            raise DomainError("Рейтинг не может быть отрицательным.")
        tournament = shared.tournament_service.ensure_tournament()
        if tournament.prepared:
            raise DomainError("После /prepare_tournament менять рейтинг запрещено.")
        player = shared.player_repo.get_by_id(player_id)
        if player is None:
            raise DomainError("Игрок не найден.")
        if player.rating == rating:
            await message.answer(f"Рейтинг игрока {player.full_name} уже равен {rating}.")
            return
        updated = shared.registration_service.set_rating(player_id, rating)
        shared.log_ok(actor, "/set_player_rating", f"player:{updated.id}", {"rating": updated.rating})
        response = f"Новый рейтинг игрока {updated.full_name}: {updated.rating}"
        if pending_was_prepared:
            response += ". Подготовленные пары сброшены, переподготовьте тур перед запуском."
        await message.answer(response)
