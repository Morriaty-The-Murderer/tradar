# Contributing

Thanks for working on Tradar.

## Development Setup

```bash
uv sync
```

Run the main checks before opening a pull request:

```bash
uv run pytest
uv run ruff check .
uv run mypy tradar
```

Run optional golden checks when changing report structure:

```bash
uv run pytest tests/golden --run-llm-eval
```

## Pull Requests

- Work on a feature branch, not directly on `main`.
- `main` should only receive changes through pull requests.
- Keep pull requests focused.
- Include tests for behavior changes.
- Update README or docs when the public surface changes.
- Do not commit local traces, run artifacts, SQLite databases, `.env` files, or unredacted reports.

## Public Documentation Boundary

Public docs should explain how Tradar works and how to use it. Internal planning notes, local source-discovery results, and TODO checklists based on private machine state should stay outside the public branch.
