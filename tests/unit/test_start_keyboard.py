from keyboards.start import start_keyboard


def test_start_keyboard_has_two_inline_buttons() -> None:
    keyboard = start_keyboard()
    assert len(keyboard.inline_keyboard) == 1
    row = keyboard.inline_keyboard[0]
    assert len(row) == 2
    assert row[0].callback_data == "start:register"
    assert row[1].callback_data == "start:my_tournament"
    assert "Регистрация" in (row[0].text or "")
    assert "Мой турнир" in (row[1].text or "")

