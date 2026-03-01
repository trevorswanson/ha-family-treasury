# AGENTS.md

Repository guidance for future AI chats and coding sessions.

## Purpose

Build and maintain the `family_treasury` Home Assistant custom integration
with predictable behavior, strong tests, accurate documentation, and CI-safe
changes.

## Current Baseline

- Python: `3.13`
- Tested Home Assistant version: `2026.2.3`
- HACS minimum Home Assistant version: `2026.2.3` (`hacs.json`)
- Domain: `family_treasury`
- Integration version: `0.1.0` (`custom_components/family_treasury/manifest.json`)

## Fast Start

1. Install test dependencies:

   ```bash
   python3.13 -m pip install -r requirements_test.txt
   python3.13 -m pip install tox
   ```

2. Run coverage-gated tests:

   ```bash
   tox -e coverage
   ```

3. Run docs checks:

   ```bash
   tox -e docs
   ```

4. Optional diff coverage check:

   ```bash
   DIFF_COVER_COMPARE_BRANCH=origin/main tox -e diff-coverage
   ```

Devcontainer is available at `.devcontainer/devcontainer.json`.

## Architecture Map

### Runtime Code

- `custom_components/family_treasury/__init__.py`: setup/unload lifecycle
- `custom_components/family_treasury/config_flow.py`: config + options flow
- `custom_components/family_treasury/services.py`: service schemas and handlers
- `custom_components/family_treasury/services.yaml`: service UI docs
  (descriptions/examples/selectors)
- `custom_components/family_treasury/coordinator.py`: account operations,
  orchestration, catch-up behavior
- `custom_components/family_treasury/interest.py`: interest calculations and
  schedule boundaries
- `custom_components/family_treasury/storage.py`: HA `Store` persistence,
  monthly ledgers, snapshots
- `custom_components/family_treasury/sensor.py`: balance and pending-interest entities
- `custom_components/family_treasury/models.py`: domain models, parsing,
  currency precision helpers
- `custom_components/family_treasury/frontend/family-treasury-transactions-card.js`:
  Lovelace transactions card

### Documentation

- `docs/README.md`: docs index and navigation
- `docs/getting-started.md`: install/setup/start path
- `docs/accounts-and-money-movement.md`: account and transaction workflows
- `docs/services-reference.md`: service contracts and payload examples
- `docs/automations-and-examples.md`: script/automation patterns
- `docs/lovelace-card.md`: card config and behavior
- `docs/troubleshooting.md`: known issues and diagnostics
- `docs/data-model-and-behavior.md`: precision, interest, invariants, storage
  behavior

## Source of Truth Ownership

- Service behavior: `services.py` + `services.yaml` + `docs/services-reference.md`
- Card behavior: frontend JS + `docs/lovelace-card.md`
- Data/invariants: models/coordinator/storage + `docs/data-model-and-behavior.md`

## Project Invariants (Do Not Break)

- `account_id` is a slug (`cv.slug`): lowercase letters, numbers, underscores.
- Monetary state is integer-based internally (minor + micro-minor precision),
  not float.
- Withdrawals must not allow negative balances.
- Interest accrual and payout frequencies are separate and both must support
  catch-up.
- Ledger is append-only; storage is partitioned by month with snapshots for
  faster replay.
- Sensor display precision should match currency minor exponent (for example
  USD `2`, ISK `0`).
- Transaction description contract is `meta.description`.

## Docs Impact Rules

For any user-facing behavior, API, config, service, or card change:

- Update relevant docs in `docs/` in the same PR.
- Update examples when payloads/config options change.
- If no docs update is needed, PR must explicitly state why.

## When Changing Services

- Keep `services.py` schemas and `services.yaml` definitions aligned.
- In `services.yaml`, use `example:` fields (not prose examples in descriptions).
- Add/update tests in `tests/test_services.py` when service contracts change.
- Update `docs/services-reference.md` and examples for contract changes.

## CI and Quality Gates

- `tests.yml`
  - Runs `tox -e coverage`
- Enforces changed-line coverage with `diff-cover` at `100%` for
  `custom_components/family_treasury/*`
  - Posts PR coverage comment
- `docs.yml`
  - Runs docs lint/link checks
- `pr-standards.yml`
  - Enforces Conventional Commits
  - Requires PR issue reference
- `hassfest.yml`
  - Runs Home Assistant Hassfest validation

Coverage policy:

- Total coverage floor: `60%` (`COV_FAIL_UNDER`, default in `tox.ini`)
- Changed lines in integration code: `100%` in PR CI

## Contribution Expectations

- Keep changes focused; avoid unrelated refactors.
- Add tests with behavior changes, not after.
- Keep docs and runtime behavior synchronized.
- Use Conventional Commit messages:
  - `feat(scope): ...`
  - `fix(scope): ...`
  - `test(scope): ...`
  - `docs(scope): ...`

## Suggested Workflow Per Task

1. Read relevant module(s), docs pages, and tests.
2. Implement minimal, scoped change.
3. Update/extend tests for regressions and edge cases.
4. Update docs/examples impacted by the change.
5. Run `tox -e coverage` and `tox -e docs`.
6. If PR-bound, optionally run diff coverage check locally.

## Agent Completion Checklist

Before finishing a task:

- Identify impacted docs pages in `docs/`.
- Update docs and examples.
- Verify links and markdown checks pass.
- Verify code + docs tests pass.

## Release Notes Obligation

For tagged releases, include upgrade/migration notes in GitHub Releases.
At minimum include:

- Breaking changes
- User-facing changes
- Service/automation contract changes
- Dashboard/card changes
- Migration actions (if any)
