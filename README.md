<img alt="Family Treasury logo" src="https://raw.githubusercontent.com/trevorswanson/ha-family-treasury/refs/heads/main/custom_components/family_treasury/brand/logo.png" />

# Family Treasury

Family Treasury is a Home Assistant custom integration for virtual family banking.

It provides multi-account balances, configurable APR compounding logic, transaction history, and automation-friendly service calls.

## Features

- Multiple virtual accounts managed by `account_id`
- Account lifecycle services:
  - `family_treasury.create_account`
  - `family_treasury.update_account`
- Money movement services:
  - `family_treasury.deposit`
  - `family_treasury.withdraw`
  - `family_treasury.adjust_balance`
- Interest engine with separate frequencies for:
  - interest calculation (`daily`, `weekly`, `monthly`)
  - interest payout (`daily`, `weekly`, `monthly`)
- Locale-aware currency display (`currency_code` + `locale`)
- Sensors per account:
  - balance
  - pending interest
- Transaction history:
  - Lovelace card (for custom dashboards)
  - Service action `family_treasury.get_transactions` (response-capable, filter + pagination)
- Persistent storage with monthly ledger partitions and snapshots

## Roadmap

- [ ] Savings buckets/sub-accounts runtime behavior
- [ ] Account-to-account transfers
- [ ] Loan tracking or screen-time conversion features

## Installation

### HACS (recommended)

1. Open HACS
2. Add custom repository:
   - URL: `https://github.com/trevorswanson/ha-family-treasury`
   - Category: `Integration`
3. Install the integration
4. Restart Home Assistant
5. Add **Family Treasury** via **Settings -> Devices & Services**

### Manual

1. Copy `family_treasury` into:

```text
config/custom_components/
```

2. Restart Home Assistant
3. Add **Family Treasury** via **Settings -> Devices & Services**

## Configuration

Configuration is UI-driven via config flow.

Initial settings:

- `default_apr_percent`
- `interest_calc_frequency` (`daily|weekly|monthly`)
- `interest_payout_frequency` (`daily|weekly|monthly`)
- `currency_code` (ISO-4217, e.g. `USD`, `ISK`)
- `locale` (e.g. `en_US`, `is_IS`)

Options flow supports updating all defaults and applying them to existing accounts.

## Entities

For each account, Home Assistant creates two sensors (entity IDs are generated from display name):

- `sensor.<account>_balance`
- `sensor.<account>_pending_interest`

Common attributes include:

- `account_id`
- `display_name`
- `currency_code`
- `locale`
- `last_interest_calc_at`
- `last_interest_payout_at`
- `recent_transactions` (latest 10)

## Services

Service fields are fully defined in [`custom_components/family_treasury/services.yaml`](custom_components/family_treasury/services.yaml).

### Create account

```yaml
service: family_treasury.create_account
data:
  account_id: emma
  display_name: Emma
  initial_balance: 10.00
  apr_percent: 3.50
  interest_calc_frequency: daily
  interest_payout_frequency: monthly
  currency_code: USD
  locale: en_US
```

### Deposit

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 5.00
  description: Dishwasher
```

### Withdraw

```yaml
service: family_treasury.withdraw
data:
  account_id: emma
  amount: 3.00
  description: Toy purchase
```

### Adjust balance (signed)

```yaml
service: family_treasury.adjust_balance
data:
  account_id: emma
  amount: -1.50
  description: Correction
```

### Query transactions

```yaml
service: family_treasury.get_transactions
data:
  account_id: emma
  type:
    - deposit
    - withdraw
    - adjustment
    - interest_payout
  limit: 50
  offset: 0
```

## Interest Model

- Balances are stored in integer minor units (no float balances)
- Pending interest is tracked in high precision (`micro-minor`)
- Calculation and payout schedules are independent
- Payout moves accrued pending interest into principal balance
- Scheduler catches up missed windows after restarts

## Dashboard Examples

- [`examples/dashboard.yaml`](examples/dashboard.yaml)
- [`examples/scripts.yaml`](examples/scripts.yaml)

## Lovelace Card

This integration ships a custom Lovelace card:

- Type: `custom:family-treasury-transactions`
- Required config:
  - `account_id`
- Optional config:
  - `title` (default: `Recent Transactions`)
  - `page_size` (default: `10`)
  - `enable_pagination` (default: `true`)
  - `allow_page_size_override` (default: `false`)
  - `page_size_options` (default: `[5, 10, 25, 50]`)
  - `types` (optional list of transaction types to include)

Example:

```yaml
type: custom:family-treasury-transactions
title: Emma Recent Transactions
account_id: emma
page_size: 10
enable_pagination: true
allow_page_size_override: true
page_size_options:
  - 5
  - 10
  - 25
types:
  - deposit
  - withdraw
  - adjustment
  - interest_payout
```

### Resource Loading Behavior

When the integration is loaded, it automatically:

1. Serves the card JavaScript from `/family_treasury/family-treasury-transactions-card.js`
2. Registers the URL via `frontend.add_extra_js_url`
3. Creates a Lovelace storage resource entry in storage mode if one does not already exist

In standard Home Assistant setups, no manual Lovelace resource configuration is required.
If frontend or Lovelace is intentionally disabled, automatic card loading is unavailable.

## Integration Icon

This repository includes integration brand assets in:

- `custom_components/family_treasury/brand/icon.png`
- `custom_components/family_treasury/brand/logo.png`

Home Assistant support for local integration brand assets was introduced in
Home Assistant `2026.3`. If you run an older Home Assistant version, the
integration tile may still show `Icon not available` until the domain is added
to the central [home-assistant/brands](https://github.com/home-assistant/brands) repository.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for full contributor workflow, local validation, CI standards, and Conventional Commit requirements.

## License

Licensed under the [MIT License](LICENSE).

## AI Assistance Disclosure

This project is being built with AI assistance. Human maintainers review and approve architecture, implementation, and release decisions.
