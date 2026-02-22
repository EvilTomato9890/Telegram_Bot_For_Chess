"""Core service contracts for tournament operations.

This module captures service-level invariants used by handlers and storage adapters.
"""


class TournamentService:
    """Manage tournament lifecycle and command preconditions.

    Invariants:
    - Lifecycle is strictly `draft -> registration -> ongoing -> finished`.
    - Allowed transitions are forward-only; rollback is forbidden.
    - `finished` is terminal and immutable.
    - Commands must be validated against current status before mutation.
    - Match result tokens are limited to: `1-0`, `0-1`, `0.5-0.5`, `bye`, `forfeit`.
    - Result confirmations/overrides are allowed only during `ongoing` and by
      authorized roles (players for submission, opponent/admin for confirmation,
      admin/arbiter for override with reason).
    """


class PairingService:
    """Create and manage pairings for active tournaments.

    Invariants:
    - Pairings can be generated only when tournament status is `ongoing`.
    - Result input must match canonical tokens: `1-0`, `0-1`, `0.5-0.5`, `bye`, `forfeit`.
    - Result override is restricted to arbiter/admin roles and must be auditable.
    - No pairing/result mutation is allowed after tournament reaches `finished`.
    """


class TicketService:
    """Distribute support/operations tickets among maintainers.

    Invariants:
    - Automatic assignment uses least-loaded policy.
    - Least-loaded is defined as minimum `open + assigned` ticket count.
    - Terminal tickets (`resolved`, `closed`) are excluded from load calculation.
    - Tie-breaker is deterministic: fewer `assigned` tickets, then user id order.
    """
