from keyboards.player_menu import player_menu_keyboard


def test_player_menu_keyboard_contains_expected_commands() -> None:
    keyboard = player_menu_keyboard()
    texts = [button.text or "" for row in keyboard.keyboard for button in row]
    commands = {text.split()[0] for text in texts if text}
    expected = {
        "/my_next",
        "/my_score",
        "/standings",
        "/schedule",
        "/report",
        "/get_game_id",
        "/rules",
        "/help",
        "/create_ticket",
    }
    assert expected.issubset(commands)
    assert any("🗓" in text for text in texts)
    assert any("📊" in text for text in texts)

