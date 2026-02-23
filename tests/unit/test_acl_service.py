from domain.models import Role
from tests.utils import build_db_url, build_services


def test_acl_or_logic_for_multi_role_user() -> None:
    services = build_services(build_db_url("acl"))
    acl = services["acl_service"]

    # organizer from config
    assert acl.can_execute(9001, "/set_rules") is True
    # arbitrator from config
    assert acl.can_execute(9002, "/approve_result") is True
    # player role is available for every user
    assert acl.can_execute(777, "/register") is True


def test_runtime_grants_are_resolved() -> None:
    services = build_services(build_db_url("acl_grant"))
    acl = services["acl_service"]
    role_repo = services["role_repo"]

    role_repo.append(777, Role.ARBITRATOR, "grant")
    assert acl.can_execute(777, "/approve_result") is True
    role_repo.append(777, Role.ARBITRATOR, "revoke")
    assert acl.can_execute(777, "/approve_result") is False

