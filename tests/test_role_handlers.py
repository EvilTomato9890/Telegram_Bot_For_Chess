import pytest

from handlers import RoleCommandHandler
from services import AccessControlService


@pytest.fixture
def role_handler() -> RoleCommandHandler:
    service = AccessControlService(config_roles_by_user={1: {"admin"}})
    return RoleCommandHandler(access_control_service=service)


def test_grant_role_command(role_handler: RoleCommandHandler) -> None:
    message = role_handler.handle_grant(actor_id=1, raw_command="/grant_role 42 admin")

    assert "role 'admin' granted" in message


def test_revoke_role_command(role_handler: RoleCommandHandler) -> None:
    role_handler.handle_grant(actor_id=1, raw_command="/grant_role 42 arbiter")

    message = role_handler.handle_revoke(actor_id=1, raw_command="/revoke_role 42 arbiter")

    assert "role 'arbiter' revoked" in message


def test_role_command_validates_input(role_handler: RoleCommandHandler) -> None:
    with pytest.raises(ValueError, match="expected format"):
        role_handler.handle_grant(actor_id=1, raw_command="/grant_role")

    with pytest.raises(ValueError, match="user_id must be an integer"):
        role_handler.handle_grant(actor_id=1, raw_command="/grant_role bad admin")

    with pytest.raises(ValueError, match="role must be one of"):
        role_handler.handle_grant(actor_id=1, raw_command="/grant_role 42 owner")


def test_role_command_requires_acl() -> None:
    role_handler = RoleCommandHandler(access_control_service=AccessControlService())

    with pytest.raises(PermissionError, match="access denied"):
        role_handler.handle_grant(actor_id=999, raw_command="/grant_role 42 admin")
