# Tradar

**Trace Radar for Builders**

Find project signals in your agent work traces.

[English](README.md) | [简体中文](README.zh-CN.md)

Tradar is a local-first CLI that turns your coding-agent activity into an
evidence-backed project radar. It reads Codex sessions, Claude Code sessions,
project documents, and git traces, then produces a traceable HTML report with
opportunity cards, a suggested 48-hour demo, decision prompts, and debug
artifacts.

The name combines **trace** and **radar**: Tradar helps builders notice the
project signals already present in their own work traces.

Tradar is built for builders who already work through agents and want to spot
the project ideas that keep reappearing in their own work.

## What It Does

- Scans local agent work traces from Codex and Claude Code.
- Reads project intent documents such as `AGENTS.md`, `CLAUDE.md`, `README.md`,
  `CHANGELOG.md`, `docs/**/*.md`, and `notes/**/*.md`.
- Normalizes trace evidence into a local SQLite store.
- Builds a bounded evidence pack with source quotas and token budgets.
- Generates a base HTML report without calling an external analyst.
- Optionally calls a Codex analyst agent to produce project opportunity cards.
- Optionally calls a Codex HTML design subagent to enhance the report layout.
- Writes a full debug bundle so every recommendation can be traced back to
  local evidence.

## Status

Tradar is an early v0.2 CLI. It is usable from a source checkout, builds local
wheel and source distributions, and has release automation prepared for PyPI
trusted publishing.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Optional: Codex CLI, if you want to use `--agent codex` or
  `--render enhanced`
- Optional: Claude Code CLI, if you want to use `--agent claude`

## Quick Start

Install dependencies from a source checkout:

```bash
uv sync
```

Initialize local sources:

```bash
uv run tradar init \
  --project-root /path/to/project
```

`tradar init` uses `~/.codex/sessions` and `~/.claude/projects` by default.

Check source health:

```bash
uv run tradar sources doctor
```

Scan evidence without calling an analyst agent:

```bash
uv run tradar scan
```

Generate a base report from existing evidence:

```bash
uv run tradar generate --days 30
```

In an interactive terminal, `generate` opens the produced `report.html`. Use
`--no-open` for scripted runs.

Run scan + analyst generation:

```bash
uv run tradar run --days 30 --agent codex
```

Run scan + Claude Code analyst generation:

```bash
uv run tradar run --days 30 --agent claude
```

Generate an enhanced HTML report:

```bash
uv run tradar run --days 30 --agent codex --render enhanced
```

Validate a run with the golden checklist:

```bash
uv run tradar golden-check ~/.local/share/tradar/runs/<run_id>
```

Show CLI help:

```bash
uv run tradar --help
```

## Core Commands

- `tradar init`: write a local config and run source diagnostics.
- `tradar sources doctor`: inspect configured sources without scanning.
- `tradar scan`: read sources and write the local evidence store.
- `tradar generate --days 30`: generate a report from existing evidence.
- `tradar run --days 30`: run `scan + generate`.
- `tradar accept <card_id>`: mark a card as accepted in local decision state.
- `tradar snooze <card_id>`: defer a card.
- `tradar reject <card_id>`: reject a card.
- `tradar golden-check <run_dir>`: run deterministic structural checks.

## Report Modes

Tradar separates evidence processing, analyst judgment, and presentation:

- `--agent base`: deterministic local report, no external analyst call.
- `--agent codex`: sends a bounded evidence pack to the Codex analyst adapter.
- `--agent claude`: sends a bounded evidence pack to the Claude Code analyst
  adapter.
- `--render base`: deterministic base HTML renderer.
- `--render enhanced`: sends the base HTML to an HTML design subagent and falls
  back to base HTML if required sections are missing.

## Output

By default, Tradar writes local state under:

- config: `~/.config/tradar/config.toml`
- state: `~/.local/share/tradar/tradar.sqlite`
- runs: `~/.local/share/tradar/runs/<run_id>/`

Each run directory includes:

- `run.json`
- `warnings.jsonl`
- `evidence_pack.json`
- `agent_raw_output.json`
- `validated_report.json`
- `render.log`
- `report.html`

When external agent adapters are used, the run directory may also include:

- `agent_prompt.md`
- `agent_last_message.json`
- `schema_repair_prompt.md`
- `schema_repair_last_message.json`
- `html_design_prompt.md`
- `html_design_last_message.html`

## Privacy And Safety

Tradar is local-first, but its reports can include excerpts and summaries from
your local work traces. Treat run directories as private unless you have
reviewed and redacted them.

Important boundaries:

- Source content is treated as untrusted evidence, never as executable
  instructions.
- Project documents are allowlisted; Tradar does not recursively ingest every
  Markdown file in a repository.
- Evidence packs are bounded by item and token budgets before they are sent to
  an analyst adapter.
- `scan` does not call external agents.
- `generate` does not implicitly scan.
- Decision commands only write local decision state.

Do not commit local session traces, generated run directories, local SQLite
databases, or unredacted reports.

## Development

Run the test suite:

```bash
uv run pytest
```

Run optional golden fixture checks:

```bash
uv run pytest tests/golden --run-llm-eval
```

Run linting and typing:

```bash
uv run ruff check .
uv run mypy tradar
```

Enable the optional pre-push hook to run linting, typing, and tests before
pushing:

```bash
git config core.hooksPath .githooks
```

## Documentation

- [Usage guide](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Product principles](docs/product-principles.md)
- [Milestones](docs/milestones.md)
- [Open-source boundary](docs/open-source-boundary.md)
- [Privacy model](docs/privacy.md)
- [Release and PR flow](docs/release.md)
- [Example config](examples/config.toml)

## Contributing

Tradar is currently in early MVP development. Issues and pull requests are
welcome, especially around source connectors, privacy controls, report quality,
and packaging. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Repository Layout

```text
tradar/
  agent_runner/      # Codex, Claude Code, schema repair, and HTML design adapters
  cli/               # Typer CLI
  config/            # Local config and defaults
  connectors/        # Codex, Claude Code, project docs, and git parsers
  evidence/          # Normalization, packing, privacy gate, SQLite store
  golden/            # Deterministic golden report checks
  renderer/          # Base and enhanced HTML rendering
  schemas/           # Pydantic data contracts
  state/             # Local decision state
tests/
docs/
```

## Roadmap

- Improve source discovery and deduplication across noisy agent traces.
- Add richer redaction and privacy policy controls.
- Improve enhanced HTML report design quality.

## License

MIT. See [LICENSE](LICENSE).
