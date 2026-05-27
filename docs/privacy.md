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

`generate --agent codex` sends a bounded evidence pack to the Codex analyst adapter. The pack should contain summarized evidence and source metadata, not raw session transcripts.

`--render enhanced` sends base HTML to the HTML design adapter. Enhanced rendering must preserve required report sections and may fall back to base HTML.

## Reviewer Checklist

Before publishing a PR, reviewers should check:

1. No `.env` files are staged.
2. No generated `run_*`, `runs/`, or `reports/` directories are staged.
3. No SQLite databases are staged.
4. No raw session JSONL files are staged.
5. No private local paths are present in public docs or examples.
6. No credential-like strings appear in public files.
