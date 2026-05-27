# Open-source Boundary

This repository should only publish code, tests, sanitized fixtures, public docs, and safe examples.

## Publish

- `README.md`
- `README.zh-CN.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `.github/`
- `.gitleaks.toml`
- `pyproject.toml`
- `uv.lock`
- `tradar/`
- `tests/`
- `docs/architecture.md`
- `docs/milestones.md`
- `docs/usage.md`
- `docs/open-source-boundary.md`
- `docs/privacy.md`
- `docs/release.md`
- `examples/config.toml`

## Keep Local Or Private

- Internal implementation plans.
- Source-discovery notes based on local machine samples.
- Raw Codex or Claude Code sessions.
- Generated run directories.
- Local SQLite databases.
- Unredacted HTML reports.
- Temporary prompts containing real work traces.
- Any `.env` or machine-specific config file.

## Current Local-only Location

Local-only planning material is stored under `private/`, which is ignored by git in this public branch. If those files need git history, keep them in a private branch or a separate private repository rather than staging them into the public branch.

## Pre-push Checklist

Before opening a public PR:

1. Run the test suite and static checks.
2. Search for legacy package and data-directory names.
3. Search for credential-like strings.
4. Inspect `git status --short` and stage only intended public files.
5. Confirm no files under `private/`, local run directories, SQLite databases, or `.env` files are staged.
6. Open changes against `main` through a pull request; do not commit or push directly to `main`.
