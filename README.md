# Telegram_Bot_For_Chess

Telegram bot for chess tournament in MIPT.

## Project layout

- `bot/` — application factory and runtime bootstrap.
- `domain/` — domain entities/value objects (reserved for expansion).
- `services/` — business service contracts.
- `repositories/` — persistence adapters (reserved for expansion).
- `handlers/` — telegram command/update handlers (reserved for expansion).
- `keyboards/` — telegram keyboard builders (reserved for expansion).
- `infra/` — infrastructure concerns (`config`, `logging`).
- `tests/` — automated tests.

## Configuration

Configuration is loaded from `.env` via `infra/config.py`.

Required variables:

- `TOKEN`
- `DB_URL`

Optional variables:

- `ADMIN_IDS` (comma-separated integers)
- `ARBITRS_IDS` (comma-separated integers)
- `TIMEZONE` (default: `UTC`)
- `LOG_LEVEL` (default: `INFO`)
- `AUDIT_LOG_PATH` (default: `logs/audit.log`)

## Assumptions

The project relies on explicit product assumptions for tournament lifecycle, command validation, result handling, and ticket load balancing. A full normative description is maintained in [`docs/assumptions.md`](docs/assumptions.md).
