# Telegram_Bot_For_Chess

Telegram bot for chess tournament in MIPT.

## Assumptions

The project relies on explicit product assumptions for tournament lifecycle, command validation, result handling, and ticket load balancing. A full normative description is maintained in [`docs/assumptions.md`](docs/assumptions.md).

### Tournament lifecycle

- `draft -> registration -> ongoing -> finished`
- Status transitions are strictly forward-only according to the allowed transition table in `docs/assumptions.md`.

### Command validation by status

Commands are validated against tournament status before execution. If a command is not allowed for the current status, it must be rejected with a clear validation error.

### Match result format

Only the following values are accepted:

- `1-0`
- `0-1`
- `0.5-0.5`
- `bye`
- `forfeit`

### Result confirmation and override

Result confirmation and overrides are role- and status-dependent and are described in `docs/assumptions.md`.

### Ticket routing policy

"Least-loaded" means the assignee with the smallest number of tickets in `open` + `assigned` states.
