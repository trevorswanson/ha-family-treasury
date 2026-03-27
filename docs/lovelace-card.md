# Lovelace Card

Family Treasury ships these Lovelace cards:

- `custom:family-treasury-transactions`
- `custom:family-treasury-account-summary`

## Card Type

```yaml
type: custom:family-treasury-transactions
```

## Visual Editor

The card now supports the Lovelace visual editor.

- Account selection uses a chooser populated from Family Treasury balance
  sensors.
- Transaction filtering uses checkboxes.
- New cards created through the visual editor default to all transaction types
  except `interest_accrual`.
- Account selection in the visual editor supports multiple accounts.

Existing YAML cards keep their current behavior. If `types` is omitted in YAML,
the card still shows all transaction types.

## Required Config

- One of:
- `account_id`: target account slug
- `account_ids`: target account slug list

## Optional Config

- `title` (default: `Recent Transactions`)
- `show_account_name` (default: `true`)
- `page_size` (default: `10`)
- `enable_pagination` (default: `true`)
- `allow_page_size_override` (default: `false`)
- `page_size_options` (default: `[5, 10, 25, 50]`)
- `types` (default: `[deposit, withdraw, adjustment, interest_accrual,`
  `interest_payout, transfer_out, transfer_in]`)

If `types` is omitted, all transaction types are shown.

The card displays these columns:

- occurred timestamp
- account slug when multiple accounts are selected
- transaction type
- description from `meta.description`
- amount
- running balance after the transaction for single-account views

## Example: Hide Interest Accrual Rows

```yaml
type: custom:family-treasury-transactions
title: Emma's Recent Transactions
account_id: emma
page_size: 10
enable_pagination: true
types:
  - deposit
  - withdraw
  - adjustment
  - interest_payout
```

## Example: Multiple Accounts

```yaml
type: custom:family-treasury-transactions
title: Household Transactions
account_ids:
  - emma
  - sam
page_size: 10
enable_pagination: true
types:
  - deposit
  - withdraw
  - adjustment
  - interest_payout
```

## Pagination Behavior

- When `enable_pagination` is true, the card fetches by `limit` + `offset`
  and shows Prev/Next controls.
- When disabled, only first page is shown.
- Runtime page-size selector appears only when `allow_page_size_override` is true.
- The account name line under the title can be hidden with `show_account_name: false`.
- In the visual editor, `page_size_options` is only shown when viewer override
  is enabled.
- In the visual editor, the viewer page-size override toggle is only shown when
  pagination is enabled.
- Running balance is hidden automatically when multiple accounts are selected.

## Loading and Resource Behavior

The integration automatically:

1. Serves card JavaScript from `/family_treasury/family-treasury-transactions-card.js`
2. Registers it via `frontend.add_extra_js_url`

It does not modify Home Assistant's Lovelace resource storage. This avoids
the integration taking ownership of shared frontend resources during startup
or shutdown.

## Troubleshooting

- If card does not appear after update:
  - Restart Home Assistant
  - Hard-refresh browser/app cache
  - Verify `/family_treasury/family-treasury-transactions-card.js` is reachable
- If transactions load but look wrong:
  - Verify `account_id` slug
  - Verify service query in Developer Tools using same type filters

## Account Summary Card

Family Treasury also ships `custom:family-treasury-account-summary`.

### Summary Required Config

- `parent_account_id`: the parent account slug to summarize

### Summary Optional Config

- `title` (default: `Account Summary`)
- `show_pending_interest` (default: `true`)
- `show_next_interest_payout` (default: `true`)

### Behavior

- Shows the selected parent account and all active direct child accounts.
- Displays current balance for every shown account.
- Can optionally display pending interest and next interest payout date.
- The visual editor exposes checkboxes for both optional columns, enabled by
  default.

### Example

```yaml
type: custom:family-treasury-account-summary
title: Emma Account Summary
parent_account_id: emma
show_pending_interest: true
show_next_interest_payout: true
```
