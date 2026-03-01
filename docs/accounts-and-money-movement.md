# Accounts and Money Movement

## Account Model

Each account has a stable slug `account_id` and mutable settings:

- `display_name`
- `active`
- `apr_percent`
- interest frequencies (`calc` and `payout`)
- `currency_code`
- `locale`

Behavioral notes:

- `account_id` must be slug-safe (lowercase letters, numbers, underscores).
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

## Validation Rules

- Deposits must be positive.
- Withdrawals must be positive.
- Adjustments must be non-zero and may be positive or negative.
- Withdrawals and negative adjustments cannot push balance below zero.

## Child Accounts / Buckets

Family Treasury defines account type constants for primary and bucket-style
accounts, but full runtime child-account workflows are still roadmap work.

Current status:

- Supported and documented runtime flows are primary account operations.
- Use roadmap/issues for sub-account feature tracking.
