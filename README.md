# Family Treasury

![Family Treasury logo](custom_components/family_treasury/brand/logo.png)

Family Treasury is a Home Assistant custom integration for virtual family banking.

It supports multi-account balances, service-driven money movement, interest
accrual/payout, transaction history, and a Lovelace transactions card.

## Quick Install

### HACS (recommended)

1. Open HACS.
2. Add custom repository:
   - URL: `https://github.com/trevorswanson/ha-family-treasury`
   - Category: `Integration`
3. Install Family Treasury.
4. Restart Home Assistant.
5. Add **Family Treasury** via **Settings -> Devices & Services**.

### Manual

1. Copy `family_treasury` into `config/custom_components/`.
2. Restart Home Assistant.
3. Add **Family Treasury** via **Settings -> Devices & Services**.

## Minimal Quickstart

Create an account:

```yaml
service: family_treasury.create_account
data:
  account_id: emma
  display_name: Emma
  initial_balance: 10.00
```

Deposit funds:

```yaml
service: family_treasury.deposit
data:
  account_id: emma
  amount: 5.00
  description: Weekly allowance
```

## Documentation

Detailed docs live in [`docs/`](docs/README.md):

- [Getting Started](docs/getting-started.md)
- [Accounts and Money Movement](docs/accounts-and-money-movement.md)
- [Services Reference](docs/services-reference.md)
- [Automations and Examples](docs/automations-and-examples.md)
- [Lovelace Card](docs/lovelace-card.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Data Model and Behavior](docs/data-model-and-behavior.md)

## Examples

- [`examples/dashboard.yaml`](examples/dashboard.yaml)
- [`examples/scripts.yaml`](examples/scripts.yaml)

## Roadmap

- [ ] Savings buckets/sub-accounts runtime behavior
- [ ] Advanced cross-bucket transfer policies
- [ ] Expanded loan tools (payment schedules, terms, automation helpers)

## Integration Icon

This repository includes integration brand assets in:

- `custom_components/family_treasury/brand/icon.png`
- `custom_components/family_treasury/brand/logo.png`

Home Assistant support for local integration brand assets was introduced in
Home Assistant `2026.3`. If you run an older Home Assistant version, the
integration tile may still show `Icon not available` until the domain is
added to the central
[home-assistant/brands](https://github.com/home-assistant/brands) repository.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under the [MIT License](LICENSE).

## AI Assistance Disclosure

This project is being built with AI assistance. Human maintainers review and
approve architecture, implementation, and release decisions.
