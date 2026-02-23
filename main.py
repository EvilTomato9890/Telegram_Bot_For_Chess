"""Main entrypoint for Telegram chess bot."""

from pathlib import Path

from bot.app import create_app


def main() -> None:
    dotenv_path = Path(__file__).resolve().parent / ".env"
    app = create_app(dotenv_path=dotenv_path)
    app.run()


if __name__ == "__main__":
    main()
