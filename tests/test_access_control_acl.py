from handlers import HelpCommandHandler
from services.access_control import AccessControlService


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
