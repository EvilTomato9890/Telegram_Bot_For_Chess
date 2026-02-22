import pytest

from validators import parse_positive_int, validate_role


def test_parse_positive_int() -> None:
    assert parse_positive_int("15", field_name="id") == 15

    with pytest.raises(ValueError, match="must be an integer"):
        parse_positive_int("x", field_name="id")

    with pytest.raises(ValueError, match="must be positive"):
        parse_positive_int("0", field_name="id")


def test_validate_role() -> None:
    assert validate_role(" Admin ") == "admin"

    with pytest.raises(ValueError, match="role must be one of"):
        validate_role("owner")
