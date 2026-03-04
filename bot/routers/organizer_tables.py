"""Admin handlers for tournament tables."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from domain.exceptions import DomainError
from domain.models import Table

from .organizer_shared import OrganizerShared


def register_table_handlers(router: Router, shared: OrganizerShared) -> None:
    """Register table CRUD handlers on the provided router."""

    @router.message(Command("tables"))
    async def tables_handler(message: Message) -> None:
        shared.admin_check(message, "/tables")
        tables = shared.table_repo.list_all()
        if not tables:
            await message.answer("Столы не добавлены.")
            return
        lines = []
        for table in tables:
            lines.append(f"Стол {table.number}: {table.location}")
        await message.answer("\n".join(lines))

    @router.message(Command("add_table"))
    async def add_table_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/add_table")
        payload = (message.text or "").removeprefix("/add_table").strip()
        if not payload:
            raise DomainError("Формат: /add_table <номер> [локация]")
        if "|" in payload:
            raise DomainError("Описание места удалено. Используйте: /add_table <номер> [локация]")

        parts = payload.split(maxsplit=1)
        number = shared.parse_int(parts[0], field="номер стола")
        if shared.table_repo.get_by_number(number) is not None:
            raise DomainError("Стол с таким номером уже существует.")

        location = parts[1].strip() if len(parts) > 1 else "Локация не указана"
        if not location:
            location = "Локация не указана"

        shared.table_repo.add(Table(id=None, number=number, location=location, place_hint=None))
        shared.log_ok(actor, "/add_table", f"table:{number}", {"location": location})
        await message.answer(f"Стол {number} добавлен.")

    @router.message(Command("remove_table"))
    async def remove_table_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/remove_table")
        parts = (message.text or "").split()
        if len(parts) != 2:
            raise DomainError("Формат: /remove_table <номер>")
        number = shared.parse_int(parts[1], field="номер стола")

        if shared.table_repo.get_by_number(number) is None:
            raise DomainError("Стол не найден.")

        current_round = shared.round_repo.get_current()
        if current_round is not None and current_round.id is not None:
            for game in shared.game_repo.list_by_round(current_round.id):
                if game.board_number == number:
                    raise DomainError("Нельзя удалить стол: он используется в текущем туре.")

        removed = shared.table_repo.remove_by_number(number)
        if not removed:
            raise DomainError("Стол не найден.")
        shared.log_ok(actor, "/remove_table", f"table:{number}", {"removed": True})
        await message.answer(f"Стол {number} удален.")


