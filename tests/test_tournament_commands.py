import pytest

from handlers import CommandDispatcher, CommandError
from keyboards import build_start_keyboard_message


def test_happy_path_through_finish() -> None:
    dispatcher = CommandDispatcher()

    assert dispatcher.execute("/create_tournament") == "Tournament created"
    assert dispatcher.execute("/open_registration") == "Registration opened"
    assert dispatcher.execute("/set_player_rating alice 1600") == "Rating for alice set to 1600"
    assert dispatcher.execute("/set_round_number 2") == "Round number set to 2"
    assert dispatcher.execute("/prepare_turnament") == "Tournament prepared"
    assert dispatcher.execute("/start_tournament") == "Tournament started, round 1 opened"
    assert dispatcher.execute("/end_round") == "Round 1 ended"
    assert dispatcher.execute("/next_round") == "Round 2 opened"
    assert dispatcher.execute("/end_round") == "Round 2 ended"
    assert dispatcher.execute("/finish_tournament") == "Tournament finished"


def test_cannot_set_rating_after_prepare_turnament() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")
    dispatcher.execute("/set_player_rating alice 1600")
    dispatcher.execute("/set_round_number 1")
    dispatcher.execute("/prepare_turnament")

    with pytest.raises(CommandError, match="Cannot change player ratings"):
        dispatcher.execute("/set_player_rating alice 1700")


def test_cannot_open_next_round_before_closing_current_one() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")
    dispatcher.execute("/set_round_number 2")
    dispatcher.execute("/prepare_turnament")
    dispatcher.execute("/start_tournament")

    with pytest.raises(CommandError, match="Cannot generate/start next round"):
        dispatcher.execute("/next_round")


def test_cannot_finish_before_last_round() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")
    dispatcher.execute("/set_round_number 2")
    dispatcher.execute("/prepare_turnament")
    dispatcher.execute("/start_tournament")
    dispatcher.execute("/end_round")

    with pytest.raises(CommandError, match="before the last round"):
        dispatcher.execute("/finish_tournament")


def test_undo_last_action_reverts_state() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")

    assert dispatcher.execute("/undo_last_action") == "Undone: /open_registration"
    with pytest.raises(CommandError, match="after registration is opened"):
        dispatcher.execute("/prepare_turnament")


def test_aliases_and_validation_errors() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")
    dispatcher.execute("/set_round_number 1")
    assert dispatcher.execute("/prepare_tournament") == "Tournament prepared"

    with pytest.raises(CommandError, match="Usage: /round <n>"):
        dispatcher.execute("/round xyz")


def test_tournament_status_alias_and_parse_errors() -> None:
    dispatcher = CommandDispatcher()
    assert dispatcher.execute("/tournament_status") == "status=not_created, rounds=0"

    with pytest.raises(CommandError, match="Usage: /set_round_number <n>"):
        dispatcher.execute("/set_round_number one")

    with pytest.raises(CommandError, match="Usage: /set_player_rating <player> <rating>"):
        dispatcher.execute("/set_player_rating alice ten")


def test_player_commands_are_available() -> None:
    dispatcher = CommandDispatcher()

    assert "Правила" in dispatcher.execute("/rules")
    assert dispatcher.execute("/get_game_id").startswith("Your current game id:")
    assert dispatcher.execute("/my_next").startswith("Your next game:")
    assert dispatcher.execute("/schedule") == "Schedule is not published yet"
    assert dispatcher.execute("/my_score") == "Your score: 0.0"
    assert dispatcher.execute("/register") == "You are registered for the tournament"
    assert dispatcher.execute("/standings") == "Standings are available: 1 players"


def test_ticket_and_result_flow_for_player_and_arbitrator() -> None:
    dispatcher = CommandDispatcher()

    assert dispatcher.execute("/report R1-B1 1-0").endswith("awaits arbitrator approval")
    assert dispatcher.execute("/approve_result R1-B1") == "Result for R1-B1 approved"

    assert dispatcher.execute("/create_ticket wrong pairing") == "Ticket #1 created: wrong pairing"
    assert dispatcher.execute("/close_ticket 1") == "Ticket #1 closed"

    with pytest.raises(CommandError, match="not found"):
        dispatcher.execute("/close_ticket 1")


def test_usage_and_arbitrator_validation_errors_are_consistent() -> None:
    dispatcher = CommandDispatcher()

    with pytest.raises(CommandError, match="Usage: /create_ticket <topic>"):
        dispatcher.execute("/create_ticket")

    with pytest.raises(CommandError, match="No reported result for R2-B1"):
        dispatcher.execute("/approve_result R2-B1")


def test_help_messages_and_keyboard_payload() -> None:
    dispatcher = CommandDispatcher()

    assert "/rules" in dispatcher.execute("/help")
    assert "/approve_result" in dispatcher.execute("/help arbitrator")

    message = build_start_keyboard_message()
    assert message.buttons == ("регистрация", "текущая информация")
    assert "Добро пожаловать" in message.text


def test_notifications_on_round_lifecycle_rules_and_finish_position() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")
    dispatcher.execute("/set_round_number 1")
    dispatcher.execute("/prepare_turnament")
    dispatcher.execute("/register")
    dispatcher.service.state.player_scores["me"] = 2.0
    dispatcher.service.state.player_scores["alice"] = 3.0

    dispatcher.execute("/start_tournament")
    dispatcher.execute("/update_rules")
    dispatcher.execute("/end_round")
    dispatcher.execute("/finish_tournament")

    assert dispatcher.service.notification_service.messages == [
        "Notification: round 1 started",
        "Notification: pairings for round 1 published",
        "Notification: tournament rules updated",
        "Notification: round 1 ended",
        "Notification: tournament finished, me position #2",
    ]


def test_schedule_returns_round_windows_when_rounds_are_configured() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/set_round_number 2")

    assert dispatcher.execute("/schedule") == (
        "Schedule windows:\n"
        "Round 1: day 1 10:00-22:00\n"
        "Round 2: day 3 10:00-22:00"
    )


def test_critical_commands_are_logged_to_audit_and_console(
    capsys: pytest.CaptureFixture[str],
) -> None:
    dispatcher = CommandDispatcher()

    dispatcher.execute("/create_tournament")
    captured = capsys.readouterr()

    assert "[critical] actor=system command=/create_tournament" in captured.out
    assert len(dispatcher.service.audit_log) == 1
    record = dispatcher.service.audit_log[0]
    assert record.command == "/create_tournament"
    assert record.actor == "system"
    assert record.outcome == "Tournament created"


def test_update_rules_command_is_exposed_by_dispatcher() -> None:
    dispatcher = CommandDispatcher()

    assert dispatcher.execute("/update_rules") == "Rules updated"
