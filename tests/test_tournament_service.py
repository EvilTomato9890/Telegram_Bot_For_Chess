from types import SimpleNamespace

from bot.services.tournament import InsufficientTablesError, TournamentService
from bot.utils.formatting import format_round_game


class _DummyRepo:
    async def create(self, rounds_count: int, rules_text: str = ""):
        raise NotImplementedError


def _service() -> TournamentService:
    return TournamentService(tournaments=_DummyRepo(), players=_DummyRepo())


def _table(*, table_id: int, number: int, is_active: bool = True):
    return SimpleNamespace(id=table_id, number=number, is_active=is_active)


def test_assign_tables_sets_sequential_board_numbers_and_table_ids() -> None:
    service = _service()
    pairings = [(10, 20), (30, 40), (50, None)]
    tables = [
        _table(table_id=7, number=15),
        _table(table_id=9, number=9),
    ]

    assignments = service.assign_tables(pairings, tables)

    assert [assignment.board_no for assignment in assignments] == [1, 2]
    assert [assignment.table_id for assignment in assignments] == [9, 7]
    assert [assignment.table_number for assignment in assignments] == [1, 2]


def test_assign_tables_raises_when_tables_are_not_enough() -> None:
    service = _service()
    pairings = [(1, 2), (3, 4)]
    tables = [_table(table_id=1, number=1)]

    try:
        service.assign_tables(pairings, tables)
    except InsufficientTablesError as exc:
        assert "Добавьте столы" in str(exc)
    else:
        raise AssertionError("Expected InsufficientTablesError")


def test_format_round_game_includes_location_and_seat() -> None:
    text = format_round_game(
        round_number=3,
        table_number=4,
        color="белые",
        opponent="@opponent",
        location="Левый зал",
        seat="A",
    )

    assert text == "Тур 3: стол 4, место A, цвет белые, соперник @opponent, локация: Левый зал"
