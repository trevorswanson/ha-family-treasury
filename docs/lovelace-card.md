# Lovelace Card

Family Treasury ships `custom:family-treasury-transactions` for transaction display.

## Card Type

```yaml
type: custom:family-treasury-transactions
```

## Required Config

- `account_id`: target account slug

## Optional Config

- `title` (default: `Recent Transactions`)
- `page_size` (default: `10`)
- `enable_pagination` (default: `true`)
- `allow_page_size_override` (default: `false`)
- `page_size_options` (default: `[5, 10, 25, 50]`)
- `types` (default: `[deposit, withdraw, adjustment, interest_accrual,`
  `interest_payout, transfer_out, transfer_in]`)

If `types` is omitted, all transaction types are shown.

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

## Pagination Behavior

- When `enable_pagination` is true, the card fetches by `limit` + `offset`
  and shows Prev/Next controls.
- When disabled, only first page is shown.
- Runtime page-size selector appears only when `allow_page_size_override` is true.

## Loading and Resource Behavior

The integration automatically:

1. Serves card JavaScript from `/family_treasury/family-treasury-transactions-card.js`
2. Registers it via `frontend.add_extra_js_url`
3. Adds Lovelace storage resource entry in storage mode when needed

## Troubleshooting

- If card does not appear after update:
  - Restart Home Assistant
  - Hard-refresh browser/app cache
  - Verify `/family_treasury/family-treasury-transactions-card.js` is reachable
- If transactions load but look wrong:
  - Verify `account_id` slug
  - Verify service query in Developer Tools using same type filters
