# Getting Started

## Prerequisites

- Home Assistant version: `2026.2.3` or newer (current baseline)

## Installation

### HACS (recommended)

1. Open HACS.
2. Add custom repository:
   - URL: `https://github.com/trevorswanson/ha-family-treasury`
   - Category: `Integration`
3. Install Family Treasury.
4. Restart Home Assistant.
5. Add Family Treasury from **Settings -> Devices & Services**.

### Manual

1. Copy `family_treasury` to `config/custom_components/`.
2. Restart Home Assistant.
3. Add Family Treasury from **Settings -> Devices & Services**.

## Initial Configuration

The config flow captures global defaults:

- `default_apr_percent`
- `interest_calc_frequency` (`daily`, `weekly`, `monthly`)
- `interest_payout_frequency` (`daily`, `weekly`, `monthly`)
- `currency_code` (ISO 4217, for example `USD`)
- `locale` (for example `en_US`)

## Create Your First Account

Use **Developer Tools -> Actions**:

```yaml
service: family_treasury.create_account
data:
  account_id: emma
  display_name: Emma
  initial_balance: 10.00
```

## Validate Successful Setup

1. Confirm entities exist:
   - `sensor.emma_balance`
   - `sensor.emma_pending_interest`
2. Run a test transaction:

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 1.00
  description: Test deposit
```

1. Confirm:
   - Balance sensor updates.
   - `recent_transactions` attribute includes the new transaction.

## Next Steps

- Optional: create a loan account tied to the child primary account:

```yaml
service: family_treasury.create_account
data:
  account_id: emma_loan_1
  display_name: Emma Loan #1
  account_type: loan
  parent_account_id: emma
  initial_balance: 20.00
```

- Optional: repay loan balance via transfer:

```yaml
service: family_treasury.transfer
data:
  source_account_id: emma
  destination_account_id: emma_loan_1
  amount: 2.00
  description: Weekly repayment
```

- Optional: after creating a loan, confirm loan sensors exist:
  - `sensor.emma_loan_1_balance`
  - `sensor.emma_loan_1_loan_principal`
  - `sensor.emma_loan_1_loan_original_principal`
  - `sensor.emma_loan_1_loan_total_accrued_interest`
  - `sensor.emma_loan_1_loan_total_balance`
  - `sensor.emma_loan_1_loan_payoff_progress`

- [Accounts and Money Movement](accounts-and-money-movement.md)
- [Services Reference](services-reference.md)
- [Lovelace Card](lovelace-card.md)
