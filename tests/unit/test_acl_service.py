from domain.models import Role, Table
from tests.utils import build_db_url, build_services


def test_acl_or_logic_for_multi_role_user() -> None:
    services = build_services(build_db_url("acl"))
    acl = services["acl_service"]

    assert acl.can_execute(9001, "/set_rules") is True
    assert acl.can_execute(9002, "/approve_result") is True
    assert acl.can_execute(9002, "/ticket_queue") is True
    assert acl.can_execute(777, "/register") is True
    assert acl.can_execute(777, "/my_score") is False
    assert acl.can_execute(777, "/rules") is False
    assert acl.can_execute(777, "/schedule") is False
    assert acl.can_execute(777, "/report") is False


def test_acl_registry_contains_new_admin_commands_only() -> None:
    services = build_services(build_db_url("acl_commands"))
    acl = services["acl_service"]

    assert acl.can_execute(9001, "/prepare_tournament") is True
    assert acl.can_execute(9001, "/force_finish_tournament") is True
    assert acl.can_execute(9001, "/tournament_status") is True
    assert acl.can_execute(9001, "/delete_player") is True
    assert acl.can_execute(9001, "/announce") is True
    assert acl.can_execute(9002, "/force_finish_tournament") is False
    assert acl.can_execute(9001, "/prepare_turnament") is False
    assert acl.can_execute(9001, "/tournament_statuc") is False


def test_runtime_grants_are_resolved() -> None:
    services = build_services(build_db_url("acl_grant"))
    acl = services["acl_service"]
    role_repo = services["role_repo"]

    role_repo.append(777, Role.ARBITRATOR, "grant")
    assert acl.can_execute(777, "/approve_result") is True
    role_repo.append(777, Role.ARBITRATOR, "revoke")
    assert acl.can_execute(777, "/approve_result") is False

    role_repo.append(778, Role.ADMIN, "grant")
    assert acl.can_execute(778, "/set_rules") is True


def test_player_role_is_granted_after_registration() -> None:
    services = build_services(build_db_url("acl_player"))
    acl = services["acl_service"]
    registration = services["registration_service"]
    tournament = services["tournament_service"]
    table_repo = services["table_repo"]

    tournament.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament.open_registration()
    registration.register(777, "u777", "User 777", 1200)

    assert acl.can_execute(777, "/my_score") is True


def test_disqualified_player_is_limited_to_read_only_commands() -> None:
    services = build_services(build_db_url("acl_dq"))
    acl = services["acl_service"]
    registration = services["registration_service"]
    tournament = services["tournament_service"]
    table_repo = services["table_repo"]

    tournament.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament.open_registration()
    player = registration.register(777, "u777", "User 777", 1200)
    assert acl.can_execute(777, "/report") is True

    registration.disqualify(player.id or 0)

    assert acl.can_execute(777, "/report") is False
    assert acl.can_execute(777, "/my_next") is False
    assert acl.can_execute(777, "/create_ticket") is False
    assert acl.can_execute(777, "/register") is False
    assert acl.can_execute(777, "/help") is True
    assert acl.can_execute(777, "/rules") is True
    assert acl.can_execute(777, "/schedule") is True
    assert acl.can_execute(777, "/my_score") is True
    assert acl.can_execute(777, "/standings") is True


def test_disqualified_admin_can_execute_admin_commands() -> None:
    services = build_services(build_db_url("acl_dq_admin"))
    acl = services["acl_service"]
    registration = services["registration_service"]
    tournament = services["tournament_service"]
    table_repo = services["table_repo"]

    tournament.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    tournament.open_registration()
    player = registration.register(9001, "admin", "Admin User", 1200)
    registration.disqualify(player.id or 0)

    assert acl.can_execute(9001, "/announce") is True
    assert acl.can_execute(9001, "/set_rules") is True
