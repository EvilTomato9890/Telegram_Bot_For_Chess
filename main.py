"""Main entrypoint for Telegram chess bot."""

from bot.app import create_app


def main() -> None:
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
