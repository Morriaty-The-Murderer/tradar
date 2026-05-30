# Privacy Model

Tradar is local-first, but it reads sensitive sources by design. Treat all generated run artifacts as private until reviewed.

## Sensitive Inputs

Tradar may read:

- Codex session JSONL files;
- Claude Code project sessions;
- project documents;
- git commit subjects and optional body excerpts.

These sources can include private local paths, business context, unpublished project ideas, or excerpts from agent conversations.

## Public Repository Boundary

Safe public materials:

- source code;
- sanitized tests and fixtures;
- public docs;
- example config with placeholders;
- CI and contribution metadata.

Do not publish:

- raw agent sessions;
- local config files containing real paths;
- generated run directories;
- SQLite state databases;
- unredacted HTML reports;
- internal implementation plans or local source-discovery notes.

## Adapter Boundary

`scan` reads local sources and does not call external agents.

`generate --agent codex` and `generate --agent claude` send a bounded evidence pack to the selected analyst adapter. The pack should contain summarized evidence and source metadata, not raw session transcripts.

`--render enhanced` sends base HTML to the HTML design adapter. Enhanced rendering must preserve required report sections and may fall back to base HTML.

## Privacy Controls

Tradar keeps privacy controls explicit and local:

- The source allowlist limits project documents to `AGENTS.md`, `CLAUDE.md`,
  `README.md`, `CHANGELOG.md`, `docs/**/*.md`, and `notes/**/*.md`.
- The privacy gate redacts common credential assignments before evidence is
  normalized. Matches are recorded as `privacy.redacted:<rule>` parse warnings.
- `redaction_patterns` lets users add local regular-expression hooks without
  changing source code. These hooks run during `scan`, before content reaches
  the SQLite store or any analyst adapter.
- The evidence pack budget caps how many evidence items and approximate tokens
  can reach an analyst adapter.
- Analyst prompts use evidence titles, summaries, source metadata, recurrence,
  and confidence; raw excerpts are kept in local debug artifacts instead of the
  analyst prompt.
- `scan` never calls external agents, and `generate --agent codex` /
  `generate --agent claude` are opt-in.
- `--render enhanced` sends generated base HTML to the design adapter and falls
  back to base HTML if required report sections are missing.
- `codex_binary` and `claude_binary` only configure local executable names or
  paths. Treat wrapper scripts as trusted code, because they receive the same
  bounded prompt payload as the selected adapter.
- `save_agent_raw_output = false` disables saving the raw analyst output while
  preserving structured evidence, report, warning, and render artifacts.
- Generated run directories, local SQLite databases, and debug artifacts are
  private by default and must be reviewed before sharing.

Example local redaction policy:

```toml
redaction_patterns = ["VIP-\\d+", "CUSTOM-TOKEN-[A-Z0-9]+"]
redaction_replacement = "<REDACTED>"
```

## Reviewer Checklist

Before publishing a PR, reviewers should check:

1. No `.env` files are staged.
2. No generated `run_*`, `runs/`, or `reports/` directories are staged.
3. No SQLite databases are staged.
4. No raw session JSONL files are staged.
5. No private local paths are present in public docs or examples.
6. No credential-like strings appear in public files.
