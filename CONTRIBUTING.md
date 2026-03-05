# Contributing

Thanks for contributing to Family Treasury.

## Quick Start

### Option 1: Dev Container (recommended)

Open the repo in the dev container (`.devcontainer/devcontainer.json`).

### Option 2: Local Python

Use Python `3.14`.

```bash
python3.14 -m pip install -r requirements_test.txt
python3.14 -m pip install tox
```

## Local Validation

Run all local checks through tox:

```bash
tox
```

This runs the `coverage` environment by default.

Useful alternatives:

```bash
# Explicit coverage-gated run
tox -e coverage

# Docs lint + link validation
tox -e docs

# Diff coverage against a branch
DIFF_COVER_COMPARE_BRANCH=origin/main tox -e diff-coverage
```

## Coverage Policy

- Total coverage floor is enforced by `tox` (`COV_FAIL_UNDER`, default `60`).
- PRs must have `100%` changed-line coverage for
  `custom_components/family_treasury/*` in CI.
- CI publishes coverage artifacts and comments coverage/test stats on PRs.

## Documentation Requirements

A docs-impact decision is required for every PR.

If your PR changes behavior, APIs, services, card config, or examples, update
docs in the same PR.

Primary docs locations:

- `docs/services-reference.md` for service contract changes
- `docs/lovelace-card.md` for card behavior/config changes
- `docs/accounts-and-money-movement.md` for account workflow changes
- `docs/data-model-and-behavior.md` for invariants/precision/storage behavior
  changes
- `docs/troubleshooting.md` for new known issues or operational guidance

Also update examples when applicable:

- `examples/dashboard.yaml`
- `examples/scripts.yaml`

If no docs update is needed, state the reason explicitly in the PR.

## Pull Request Requirements

- Link an existing issue in the PR (for example `Closes #123`).
- Use Conventional Commits for all commit messages.
- Add/update tests for behavior changes.
- Keep changes scoped and avoid unrelated edits.
- Complete docs-impact checklist in PR template.

A PR template is provided at `.github/pull_request_template.md`.

## CI Workflows

- `.github/workflows/tests.yml`
  - Runs test and coverage gates
  - Enforces diff coverage on PRs
  - Comments coverage stats on PRs
- `.github/workflows/docs.yml`
  - Runs markdown lint and link validation for docs/README/CONTRIBUTING/AGENTS
- `.github/workflows/pr-standards.yml`
  - Enforces Conventional Commits
  - Requires linked issue references

## Conventional Commits

Commit messages should follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

Examples:

- `feat(interest): add monthly payout catch-up handling`
- `fix(services): reject empty account update payload`
- `test(coordinator): cover currency change constraints`
- `docs(card): add type filter examples`

## Notes

- If you add new files that should be ignored/generated, update `.gitignore`.
