# Troubleshooting

## Card Not Available in Lovelace

1. Restart Home Assistant after integration update.
2. Hard-refresh browser/app cache.
3. Open `/family_treasury/family-treasury-transactions-card.js` directly to
   confirm module load.
4. Confirm integration entry is loaded under **Settings -> Devices & Services**.

## Frontend/Resource Timing Issues

If startup order delays frontend/lovelace registration, restart once and
re-check. The integration includes retry logic when frontend/lovelace become
available.

Family Treasury does not write to Lovelace resource storage. If other custom
resources disappear after a restart, inspect Home Assistant or another
integration that manages `.storage/lovelace_resources`.

## Service Validation Errors

Use [Services Reference](services-reference.md) to verify payload shape.

Common issues:

- invalid `account_id`
- invalid amount sign/range
- invalid type filter values for `get_transactions`
- `start` later than `end`

## Unexpected Transaction Rows

If you want to hide accrual rows, filter transaction types:

- service calls: `type: [deposit, withdraw, adjustment, interest_payout]`
- Lovelace card: `types:` with same list

## Blocking/Startup Warnings

If Home Assistant reports blocking call warnings, capture logs and verify you
are on latest integration version.

## What to Include in Bug Reports

- Home Assistant version
- Family Treasury integration version
- Exact service payload or card YAML
- Relevant Home Assistant logs (trimmed to the error window)
- Reproduction steps and expected vs actual behavior

Issue tracker:

- <https://github.com/trevorswanson/ha-family-treasury/issues>
