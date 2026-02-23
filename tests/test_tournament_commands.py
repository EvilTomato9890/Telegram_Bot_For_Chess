import pytest

from handlers import CommandDispatcher, CommandError


def test_happy_path_through_finish() -> None:
    dispatcher = CommandDispatcher()

    assert dispatcher.execute("/create_tournament") == "Tournament created"
    assert dispatcher.execute("/open_registration") == "Registration opened"
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
    dispatcher.service.set_player_rating("alice", 1600)
    dispatcher.execute("/set_round_number 1")
    dispatcher.execute("/prepare_turnament")

    with pytest.raises(CommandError, match="Cannot change player ratings"):
        dispatcher.service.set_player_rating("alice", 1700)


def test_cannot_open_next_round_before_closing_current_one() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/set_round_number 2")
    dispatcher.execute("/prepare_turnament")
    dispatcher.execute("/start_tournament")

    with pytest.raises(CommandError, match="Cannot generate/start next round"):
        dispatcher.execute("/next_round")


def test_undo_last_action_reverts_state() -> None:
    dispatcher = CommandDispatcher()
    dispatcher.execute("/create_tournament")
    dispatcher.execute("/open_registration")

    assert dispatcher.execute("/undo_last_action") == "Undone: /open_registration"
    with pytest.raises(CommandError, match="Set total rounds before preparation"):
        dispatcher.execute("/prepare_turnament")
