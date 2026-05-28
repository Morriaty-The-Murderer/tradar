# Release And PR Flow

Tradar uses a PR-only workflow for `main`.

## Branch Rules

- Do not commit directly on `main`.
- Do not push directly to `main`.
- Put implementation work on `codex/*` or maintainer-owned feature branches.
- Merge into `main` only through pull requests after CI passes.

## First Repository Bootstrap

This local repository currently starts without an initial commit. A pull request needs a remote base branch, so the first public GitHub repository must be bootstrapped before this branch can become a PR.

Recommended bootstrap path:

1. Create the GitHub repository with an initial placeholder README or equivalent base commit on `main` through GitHub's repository creation flow.
2. Enable branch protection for `main` before pushing feature work.
3. Add the remote locally.
4. Fetch `origin/main`.
5. Create a local feature branch from `origin/main`.
6. Apply the open-source-ready tree on that feature branch.
7. Push the feature branch.
8. Open a pull request into `main`.

This preserves the rule that local implementation changes do not land directly on `main`.

## Required Checks

Run these before opening a PR:

```bash
uv run pytest
uv run pytest tests/golden --run-llm-eval
uv run ruff check .
uv run mypy tradar
uv run tradar --help
```

## Release Automation

The release workflow builds and tests distributions on version tags matching
`v*.*.*`. It uses PyPI trusted publishing, so no PyPI token should be stored in
the repository.

Before the first publish:

1. Create the `tradar` project on PyPI.
2. Add this GitHub repository as a trusted publisher for the `pypi` environment.
3. Confirm the release workflow has `id-token: write` permission only in the
   publish job.
4. Tag the reviewed commit, for example `v0.2.0`.

The workflow performs:

- dependency install through `uv sync --all-groups`;
- tests, lint, and type checks;
- `uv build`;
- installed CLI smoke tests from both `dist/*.whl` and `dist/*.tar.gz`;
- `uv publish` from the tagged release job.

## Safety Checks

Before pushing a branch:

```bash
rg -n "<legacy-package-or-data-directory-name>" -g '!private/**' -g '!uv.lock' -g '!*.pyc'
rg -n --hidden -g '!private/**' -g '!.git/**' -g '!*.pyc' -g '!__pycache__/**' '(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----)'
git status --short --ignored
```

Confirm that ignored local-only content stays ignored:

- `private/`
- `.env` and `.env.*`
- generated run directories
- local SQLite databases
- IDE and tool caches

## PR Body

The PR should explain:

- what changed;
- why the repository is ready for open-source review;
- what was intentionally kept private;
- which checks passed;
- whether the license choice has been confirmed.
