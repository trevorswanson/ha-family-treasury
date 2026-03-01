# Data Model and Behavior

## Monetary Precision Model

Family Treasury uses integer-backed storage for monetary correctness:

- account balances in **minor units** (`balance_minor`), for example
  `balance_minor: 1234` for $12.34
- pending interest in **micro-minor units**
  (`pending_interest_micro_minor`), for example
  `pending_interest_micro_minor: 1` for $0.00000001

This avoids floating-point drift in core accounting state.

## Formatting vs Storage

- Storage is integer-based.
- Display formatting is locale/currency aware.
- Sensor precision follows currency exponent (for example USD `2`, ISK `0`).

## Interest Semantics

Interest has two independent schedules:

- accrual frequency (`daily`, `weekly`, `monthly`)
- payout frequency (`daily`, `weekly`, `monthly`)

Behavior:

- accrual accumulates into pending interest
- payout transfers payable pending amount to principal
- scheduler performs catch-up processing after downtime/restart

## Transaction Semantics

Transactions are append-only ledger entries with fields including:

- `tx_id`
- `account_id`
- `type`
- `amount_minor`
- `balance_after_minor`
- `meta`

Description is carried as `meta.description`.

## Storage Model

- Account metadata and snapshots use Home Assistant `Store`.
- Ledger transactions are partitioned by month.
- Snapshots improve replay/load behavior for long histories.

## Invariants

- `account_id` is slug-safe.
- Withdrawals and negative adjustments cannot create negative balances.
- Ledger entries are appended, not in-place rewritten.
- Currency changes on non-empty accounts are restricted.
