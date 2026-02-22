# Assumptions

This document defines domain rules that services and handlers must treat as invariants.

## 1. Tournament lifecycle

Canonical lifecycle:

`draft -> registration -> ongoing -> finished`

### Allowed transitions

| From status   | To status      | Allowed |
|---------------|----------------|---------|
| `draft`       | `registration` | ✅      |
| `draft`       | `ongoing`      | ❌      |
| `draft`       | `finished`     | ❌      |
| `registration`| `ongoing`      | ✅      |
| `registration`| `finished`     | ❌      |
| `ongoing`     | `finished`     | ✅      |
| `ongoing`     | `draft`        | ❌      |
| `finished`    | any other      | ❌      |

Rules:

- Transitions are forward-only; rollback is prohibited.
- `finished` is terminal.

## 2. Command validation rules by tournament status

| Command type | `draft` | `registration` | `ongoing` | `finished` |
|--------------|---------|----------------|-----------|------------|
| Configure tournament settings | ✅ | ⚠️ (read-only except minor metadata) | ❌ | ❌ |
| Register / unregister players | ❌ | ✅ | ❌ | ❌ |
| Start tournament | ❌ | ✅ | ❌ | ❌ |
| Generate pairings | ❌ | ❌ | ✅ | ❌ |
| Submit match result | ❌ | ❌ | ✅ | ❌ |
| Confirm / override result | ❌ | ❌ | ✅ | ❌ |
| Finish tournament | ❌ | ❌ | ✅ | ❌ |

Validation policy:

- Every command checks status first.
- If status is invalid for command, return a domain validation error and perform no state mutation.

## 3. Result format

Accepted result values are exactly:

- `1-0`
- `0-1`
- `0.5-0.5`
- `bye`
- `forfeit`

Normalization and validation:

- Values are case-sensitive exact tokens.
- Any other representation (`1:0`, `draw`, etc.) is invalid.
- `bye` and `forfeit` are system/arbiter-controlled outcomes.

## 4. Who may confirm or override result

During `ongoing` status only:

- **Players** can submit a proposed result for their own pairing.
- **Opponent** can confirm proposed result.
- **Arbiter/Admin** can confirm any pairing result.
- **Arbiter/Admin** can override any result with mandatory reason logging.
- **Players** cannot override a confirmed result.

After `finished`:

- No confirmations or overrides are allowed.

## 5. Least-loaded ticket assignment

For automatic ticket routing, **least-loaded** means:

- Minimize `open + assigned` ticket count for candidate assignees.
- Ignore tickets in terminal states (`resolved`, `closed`).
- Tie-breaker: lowest `assigned` count first, then deterministic user id order.
