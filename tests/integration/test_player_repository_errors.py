import pytest

from domain.exceptions import DomainError
from domain.models import Player
from tests.utils import build_db_url, build_services


def test_player_repo_add_raises_domain_error_on_duplicate_telegram_id() -> None:
    services = build_services(build_db_url("player_repo_duplicate"))
    player_repo = services["player_repo"]

    player_repo.add(Player(id=None, telegram_id=101, username="u1", full_name="A", rating=1500))

    with pytest.raises(DomainError, match="telegram_id"):
        player_repo.add(Player(id=None, telegram_id=101, username="u2", full_name="B", rating=1400))
