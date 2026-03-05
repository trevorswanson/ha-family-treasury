# Accounts and Money Movement

## Account Model

Each account has a stable slug `account_id` and mutable settings:

- `display_name`
- `active`
- `account_type` (`primary`, `bucket`, `loan`)
- `parent_account_id` (for non-primary child accounts)
- `apr_percent`
- interest frequencies (`calc` and `payout`)
- `currency_code`
- `locale`

Behavioral notes:

- `account_id` must be slug-safe (lowercase letters, numbers, underscores).
- Loans are explicit accounts (`account_type: loan`) tied to a primary parent account.
- Currency changes are restricted on non-empty accounts.
- Account values are internally integer-based for precision.

## Core Money Movement Actions

### Deposit

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 5.00
  description: Weekly allowance
```

### Withdraw

```yaml
service: family_treasury.withdraw
data:
  account_id: emma
  amount: 3.50
  description: Book purchase
```

### Adjust Balance (signed)

```yaml
service: family_treasury.adjust_balance
data:
  account_id: emma
  amount: -1.00
  description: Correction
```

### Transfer (including Loan Repayment)

```yaml
service: family_treasury.transfer
data:
  source_account_id: emma
  destination_account_id: emma_loan_1
  amount: 2.00
  description: Weekly repayment
```

## Validation Rules

- Deposits must be positive.
- Withdrawals must be positive.
- Adjustments must be non-zero and may be positive or negative.
- Non-loan withdrawals and negative adjustments cannot push balance below zero.
- Loan accounts cannot be used with `deposit` or `withdraw`.
- Loan repayments must use `transfer` from the loan parent primary account.
- Transfers require source/destination to be in the same ownership tree.

## Loans and Child Accounts

Loan accounts are first-class accounts with debt semantics:

- Loan creation disburses principal to the linked primary account.
- Loan balances are negative, and interest compounding makes them more negative.
- Sensor semantics for loan accounts:
  - `*_balance` is the signed ledger balance (negative debt). It reflects
    principal plus any interest that has already been paid out to the ledger,
    and excludes still-pending accrued interest.
  - `*_pending_interest` is accrued interest that has not yet been paid out to
    ledger principal.
  - `*_loan_principal` is the positive view of current outstanding ledger
    principal (`abs(*_balance)`). It is not the original loan principal.
  - `*_loan_original_principal` is the original principal captured at loan
    creation. For older loans created before this field existed, a fallback
    value derived from current principal may be shown.
  - `*_loan_total_accrued_interest` is the lifetime total interest accrued for
    the loan, regardless of repayment progress.
  - `*_loan_total_balance` is a payoff-style total:
    `*_loan_principal + *_pending_interest`.
  - `*_loan_payoff_progress` is payoff progress percentage relative to
    `*_loan_original_principal`, computed from current total owed
    (`*_loan_total_balance`).
  - Example: if `*_balance = -8.00` and `*_pending_interest = 0.12`, then
    `*_loan_total_balance = 8.12`. If original principal was `20.00`, then
    `*_loan_payoff_progress = 59.40%`.

Transfers are designed to be generic so future sub-accounts/buckets/goals can
reuse the same movement model.
