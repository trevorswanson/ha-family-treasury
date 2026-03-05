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
  - savings-style accounts: payout increases balance
  - loan accounts: payout decreases balance (more negative debt)
- scheduler performs catch-up processing after downtime/restart
- loan accrual uses absolute outstanding principal as the accrual basis

Loan sensor interpretation:

- `*_balance` is ledger principal only (signed), including prior payouts and
  excluding currently pending accrued interest.
- `*_pending_interest` is accrued interest not yet paid out.
- `*_loan_principal` is `abs(*_balance)` for loan accounts (current principal,
  not original principal).
- `*_loan_original_principal` is the principal recorded at loan creation
  (`original_loan_principal_minor`). Legacy loans created before this field was
  added may show a fallback derived from current principal.
- `*_loan_total_accrued_interest` is lifetime accrued interest recorded for the
  loan (`total_accrued_interest_micro_minor`), independent of repayments.
- `*_loan_total_balance` is `*_loan_principal + *_pending_interest`, which acts
  as a payoff estimate between payout runs.
- `*_loan_payoff_progress` is payoff progress percentage:
  `max(0, min(100, (original - total_owed) / original * 100))`.

## Transaction Semantics

Transactions are append-only ledger entries with fields including:

- `tx_id`
- `account_id`
- `type`
- `amount_minor`
- `balance_after_minor`
- `meta`

Description is carried as `meta.description`.

Transfer transactions use explicit types:

- `transfer_out` (negative amount on source account)
- `transfer_in` (positive amount on destination account)

Paired transfer rows share `meta.transfer_id`.

## Storage Model

- Account metadata and snapshots use Home Assistant `Store`.
- Ledger transactions are partitioned by month.
- Snapshots improve replay/load behavior for long histories.

## Invariants

- `account_id` is slug-safe.
- Non-loan withdrawals and negative adjustments cannot create negative balances.
- Loan accounts are liability accounts and cannot become positive balances.
- Loan accounts are repaid through `transfer` from their parent primary account.
- Ledger entries are appended, not in-place rewritten.
- Currency changes on non-empty accounts are restricted.
