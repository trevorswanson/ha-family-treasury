# Contributing

Thanks for contributing to Family Treasury.

## Quick Start

### Option 1: Dev Container (recommended)

Open the repo in the dev container (`.devcontainer/devcontainer.json`).

### Option 2: Local Python

Use Python `3.13`.

```bash
python3.13 -m pip install -r requirements_test.txt
python3.13 -m pip install tox
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

# Diff coverage against a branch
DIFF_COVER_COMPARE_BRANCH=origin/main tox -e diff-coverage
```

## Coverage Policy

- Total coverage floor is enforced by `tox` (`COV_FAIL_UNDER`, default `60`).
- PRs must have `100%` changed-line coverage for `custom_components/family_treasury/*` in CI.
- CI publishes coverage artifacts and comments coverage/test stats on PRs.

## Pull Request Requirements

- Link an existing issue in the PR (for example `Closes #123`).
- Use Conventional Commits for all commit messages.
- Add/update tests for behavior changes.
- Keep changes scoped and avoid unrelated edits.

A PR template is provided at `.github/pull_request_template.md`.

## CI Workflows

- `.github/workflows/tests.yml`
  - Runs test and coverage gates
  - Enforces diff coverage on PRs
  - Comments coverage stats on PRs
- `.github/workflows/pr-standards.yml`
  - Enforces Conventional Commits
  - Requires linked issue references

## Conventional Commits

Commit messages should follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

Examples:

- `feat(interest): add monthly payout catch-up handling`
- `fix(services): reject empty account update payload`
- `test(coordinator): cover currency change constraints`

## Notes

- If you change behavior, update docs (`README.md`, examples, service docs).
- If you add new files that should be ignored/generated, update `.gitignore`.
