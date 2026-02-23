from handlers import HelpCommandHandler
from services.access_control import AccessControlService
import pytest


def test_roles_resolved_from_config_and_db() -> None:
    service = AccessControlService(
        config_roles_by_user={1: {"arbiter"}},
        db_roles_by_user={1: {"admin"}},
    )

    snapshot = service.resolve_roles(1)

    assert snapshot.roles == frozenset({"admin", "arbiter"})


def test_can_execute_supports_or_logic_for_multiple_roles() -> None:
    service = AccessControlService(config_roles_by_user={8: {"arbiter"}})

    assert service.can_execute(8, "/pairings") is True


def test_help_aggregates_unique_commands_for_all_user_roles() -> None:
    service = AccessControlService(config_roles_by_user={5: {"player", "arbiter"}})
    handler = HelpCommandHandler(access_control_service=service)

    response = handler.handle_help(actor_id=5)

    assert response.count("/register") == 1
    assert "/pairings" in response
    assert "/help" in response


def test_acl_matrix_roles_are_validated_on_service_init() -> None:
    with pytest.raises(ValueError, match="role must be one of"):
        AccessControlService(command_access_matrix={"/custom": {"owner"}})


def test_player_can_execute_report_command() -> None:
    service = AccessControlService(config_roles_by_user={11: {"player"}})

    assert service.can_execute(11, "/report") is True
    assert service.can_execute(11, "/approve_result") is False


def test_single_role_user_gets_expected_acl_commands() -> None:
    service = AccessControlService(config_roles_by_user={12: {"player"}})

    allowed = service.allowed_commands(12)

    assert "/report" in allowed
    assert "/pairings" not in allowed
    assert "/approve_result" not in allowed


def test_multi_role_user_receives_union_of_permissions() -> None:
    service = AccessControlService(config_roles_by_user={13: {"player"}, 99: {"admin"}})
    service.grant_role(actor_id=99, target_user_id=13, role="arbiter")

    assert service.can_execute(13, "/report") is True
    assert service.can_execute(13, "/approve_result") is True
    assert service.can_execute(13, "/pairings") is True
