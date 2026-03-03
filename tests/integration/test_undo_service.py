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

    result = undo_service.undo_last_admin_action(actor_id=9001)
    assert result.undone_action == "/add_table"
    assert result.snapshot_id > 0
    assert result.restored_at.tzinfo is not None
    tables = table_repo.list_all()
    assert len(tables) == 1
    assert tables[0].number == 1


def test_undo_is_scoped_to_actor() -> None:
    services = build_services(build_db_url("undo_actor_scoped"))
    table_repo = services["table_repo"]
    undo_service = services["undo_service"]

    table_repo.add(Table(id=None, number=1, location="A"))
    undo_service.snapshot(actor_id=100, action_name="/a1")
    table_repo.add(Table(id=None, number=2, location="B"))
    undo_service.snapshot(actor_id=200, action_name="/a2")
    table_repo.add(Table(id=None, number=3, location="C"))

    undo_service.undo_last_admin_action(actor_id=100)
    tables_after_actor_100 = table_repo.list_all()
    assert [table.number for table in tables_after_actor_100] == [1]

    undo_service.undo_last_admin_action(actor_id=200)
    tables_after_actor_200 = table_repo.list_all()
    assert [table.number for table in tables_after_actor_200] == [1, 2]


def test_undo_restores_state_with_games_and_foreign_keys() -> None:
    services = build_services(build_db_url("undo_fk_restore"))
    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    pairing_service = services["pairing_service"]
    table_repo = services["table_repo"]
    undo_service = services["undo_service"]
    tournament_repo = services["tournament_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="Main Hall"))
    tournament_service.open_registration()
    tournament_service.set_round_number(1, confirm=True)
    registration_service.register(1001, "u1", "Player A", 1700)
    registration_service.register(1002, "u2", "Player B", 1650)
    tournament_service.prepare_tournament()
    pairing_service.prepare_next_round_preview(1, 9001)
    tournament_service.start_tournament()
    pairing_service.generate_next_round(1, 9001, force=False)

    before = tournament_repo.get()
    assert before is not None
    undo_service.snapshot(actor_id=9001, action_name="/set_rules")
    tournament_service.set_rules("new rules")
    after_set = tournament_repo.get()
    assert after_set is not None
    assert after_set.rules_text == "new rules"

    undo_service.undo_last_admin_action(actor_id=9001)
    restored = tournament_repo.get()
    assert restored is not None
    assert restored.rules_text == before.rules_text
