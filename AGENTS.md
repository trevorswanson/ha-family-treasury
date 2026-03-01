# AGENTS.md

Repository guidance for future AI chats and coding sessions.

## Purpose

Build and maintain the `family_treasury` Home Assistant custom integration with predictable behavior, strong tests, and CI-safe changes.

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
2. Run tests with coverage gate:
   ```bash
   tox -e coverage
   ```
3. Optional diff coverage check (for PR-like validation):
   ```bash
   DIFF_COVER_COMPARE_BRANCH=origin/main tox -e diff-coverage
   ```

Devcontainer is available at `.devcontainer/devcontainer.json`.

## Architecture Map

- `custom_components/family_treasury/__init__.py`: setup/unload lifecycle
- `custom_components/family_treasury/config_flow.py`: config + options flow
- `custom_components/family_treasury/services.py`: service schemas and handlers
- `custom_components/family_treasury/services.yaml`: service UI docs (descriptions/examples/selectors)
- `custom_components/family_treasury/coordinator.py`: account operations, orchestration, catch-up behavior
- `custom_components/family_treasury/interest.py`: interest calculations and schedule boundaries
- `custom_components/family_treasury/storage.py`: HA `Store` persistence, monthly ledgers, snapshots
- `custom_components/family_treasury/sensor.py`: balance and pending-interest entities
- `custom_components/family_treasury/models.py`: domain models, parsing, currency precision helpers
- `tests/`: unit/integration coverage for all core modules

## Project Invariants (Do Not Break)

- `account_id` is a slug (`cv.slug`): lowercase letters, numbers, underscores.
- Monetary state is integer-based internally (minor + micro-minor precision), not float.
- Withdrawals must not allow negative balances.
- Interest accrual and payout frequencies are separate and both must support catch-up.
- Ledger is append-only; storage is partitioned by month with snapshots for faster replay.
- Sensor display precision should match currency minor exponent (for example USD `2`, ISK `0`).

## When Changing Services

- Keep `services.py` schemas and `services.yaml` definitions aligned.
- In `services.yaml`, use `example:` fields (not “for example …” text in descriptions).
- Add/update tests in `tests/test_services.py` when service contracts change.

## CI and Quality Gates

- `tests.yml`
  - Runs `tox -e coverage`
  - Enforces changed-line coverage with `diff-cover` at `100%` for `custom_components/family_treasury/*`
  - Posts PR coverage comment
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
- Update docs (`README.md`, `CONTRIBUTING.md`, `services.yaml`, `examples/`) when behavior changes.
- Add tests with behavior changes, not after.
- Use Conventional Commit messages:
  - `feat(scope): ...`
  - `fix(scope): ...`
  - `test(scope): ...`
  - `docs(scope): ...`

## Suggested Workflow Per Task

1. Read relevant module(s) and existing tests.
2. Implement minimal, scoped change.
3. Update/extend tests first for regressions and edge cases.
4. Run `tox -e coverage`.
5. If change is PR-bound, run diff coverage check locally.
6. Update docs/examples if user-facing behavior changed.

## Release Readiness Check (v0.1+)

- `tox -e coverage` passes
- Hassfest workflow is green
- Service docs and runtime schema are consistent
- README usage examples still match actual behavior
- No generated/local files accidentally tracked
