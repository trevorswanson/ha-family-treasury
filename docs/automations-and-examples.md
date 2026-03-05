# Automations and Examples

This page focuses on using Family Treasury service actions in scripts and automations.

Related files:

- [examples/scripts.yaml](../examples/scripts.yaml)
- [examples/dashboard.yaml](../examples/dashboard.yaml)

## Pattern: Scheduled Allowance

Use a Home Assistant automation to call `family_treasury.deposit` on a schedule.

Example action payload:

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 5.00
  description: Weekly allowance
```

## Pattern: Chore Reward Automation

Trigger deposit from task completion events (button helper, todo completion,
webhook, etc.).

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 1.50
  description: Chore reward
```

## Pattern: Purchase Deduction

Wire spend-related triggers to `family_treasury.withdraw`.

```yaml
service: family_treasury.withdraw
data:
  account_id: emma
  amount: 2.00
  description: Store purchase
```

## Pattern: Administrative Correction

Use `adjust_balance` for manual corrections and explicit audit trail.

```yaml
service: family_treasury.adjust_balance
data:
  account_id: emma
  amount: -0.50
  description: Correction for duplicate entry
```

## Querying in Automations

You can query filtered transaction history from automations or scripts:

```yaml
service: family_treasury.get_transactions
data:
  account_id: emma
  type:
    - deposit
    - interest_payout
  limit: 10
  offset: 0
```
