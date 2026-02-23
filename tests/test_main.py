from pathlib import Path
from typing import Any

import main


class _FakeApp:
    def __init__(self) -> None:
        self.ran = False

    def run(self) -> None:
        self.ran = True


def test_main_passes_repo_dotenv_path(monkeypatch: Any) -> None:
    fake_app = _FakeApp()
    captured: dict[str, Path] = {}

    def fake_create_app(*, dotenv_path: Path) -> _FakeApp:
        captured["dotenv_path"] = dotenv_path
        return fake_app

    monkeypatch.setattr(main, "create_app", fake_create_app)

    main.main()

    assert captured["dotenv_path"] == Path(main.__file__).resolve().parent / ".env"
    assert fake_app.ran is True
