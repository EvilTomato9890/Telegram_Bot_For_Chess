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
            place = f", место: {table.place_hint}" if table.place_hint else ""
            lines.append(f"Стол {table.number}: {table.location}{place}")
        await message.answer("\n".join(lines))

    @router.message(Command("add_table"))
    async def add_table_handler(message: Message) -> None:
        actor = shared.admin_check(message, "/add_table")
        payload = (message.text or "").removeprefix("/add_table").strip()
        if not payload:
            raise DomainError("Формат: /add_table <номер> <локация> [| <описание места>]")

        left = payload
        right: str | None = None
        if "|" in payload:
            left, right = payload.split("|", maxsplit=1)
        left_parts = left.strip().split(maxsplit=1)
        if len(left_parts) != 2:
            raise DomainError("Формат: /add_table <номер> <локация> [| <описание места>]")

        number = shared.parse_int(left_parts[0], field="номер стола")
        if shared.table_repo.get_by_number(number) is not None:
            raise DomainError("Стол с таким номером уже существует.")

        location = left_parts[1].strip()
        if not location:
            raise DomainError("Локация стола не может быть пустой.")
        place_hint = right.strip() if right is not None and right.strip() else None

        shared.run_with_snapshot(
            actor,
            "/add_table",
            lambda: shared.table_repo.add(Table(id=None, number=number, location=location, place_hint=place_hint)),
        )
        shared.log_ok(actor, "/add_table", f"table:{number}", {"location": location, "place_hint": place_hint or ""})
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

        removed = shared.run_with_snapshot(
            actor,
            "/remove_table",
            lambda: shared.table_repo.remove_by_number(number),
        )
        if not removed:
            raise DomainError("Стол не найден.")
        shared.log_ok(actor, "/remove_table", f"table:{number}", {"removed": True})
        await message.answer(f"Стол {number} удален.")

