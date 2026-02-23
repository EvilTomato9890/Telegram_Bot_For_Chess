from domain.models import Table
from tests.utils import build_db_url, build_services


def test_undo_restores_previous_state() -> None:
    services = build_services(build_db_url("undo"))
    table_repo = services["table_repo"]
    undo_service = services["undo_service"]

    table_repo.add(Table(id=None, number=1, location="A"))
    undo_service.snapshot(actor_id=9001, action_name="/add_table")
    table_repo.add(Table(id=None, number=2, location="B"))
    assert len(table_repo.list_all()) == 2

    undo_service.undo_last_organizer_action(actor_id=9001)
    tables = table_repo.list_all()
    assert len(tables) == 1
    assert tables[0].number == 1

