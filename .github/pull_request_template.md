## Summary

-

## Validation

- [ ] `uv run pytest`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy tradar`
- [ ] `uv run pytest tests/golden --run-llm-eval` if report schema or golden fixtures changed

## Open-source Safety

- [ ] No local agent traces, generated run directories, SQLite databases, `.env` files, or unredacted reports are included.
- [ ] No credential-like strings are introduced.
- [ ] Public docs do not include private source-discovery notes or internal implementation plans.
- [ ] Legacy package or data-directory names are not reintroduced.
