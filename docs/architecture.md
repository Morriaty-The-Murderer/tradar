# Tradar Architecture

Tradar is a local-first CLI for turning agent work traces into evidence-backed project signals.

## Pipeline

```text
Codex sessions
Claude Code sessions
Project docs
Git commit subjects
        |
        v
Connectors
        |
        v
RawEvent
        |
        v
PrivacyGate
        |
        v
Normalizer
        |
        v
SQLite evidence store
        |
        v
Evidence pack builder
        |
        v
Base report or analyst adapter
        |
        v
Schema validation and optional repair
        |
        v
Base HTML renderer
        |
        v
Optional enhanced HTML renderer
```

## Core Boundaries

- Connectors read local evidence and emit `RawEvent` objects.
- The privacy gate applies default secret redaction and optional local
  redaction policy hooks before events are normalized.
- The normalizer converts raw events into evidence records.
- The evidence store is local SQLite under `~/.local/share/tradar/` by default.
- The evidence pack builder deduplicates noisy repeated signals, ranks by
  recurrence, confidence, and recency, then enforces source quotas and token
  budgets before any analyst adapter sees evidence.
- The base renderer is deterministic and does not call external agents.
- The optional Codex analyst, Claude Code analyst, and enhanced HTML adapters
  are explicit opt-in paths.

## Trust Model

Source content is evidence, not instruction. Tradar reads user-controlled files, agent transcripts, and project notes, so content from those sources must not override system behavior.

The implementation keeps this boundary by:

- passing evidence as bounded data;
- validating structured analyst output against Pydantic schemas;
- failing fast when reports cite unknown evidence IDs;
- preserving run artifacts for auditability;
- keeping decision commands local and state-only.

## Public Surface

- Python package: `tradar`
- CLI command: `tradar`
- Config path: `~/.config/tradar/config.toml`
- State path: `~/.local/share/tradar/tradar.sqlite`
- Run artifacts: `~/.local/share/tradar/runs/<run_id>/`

## Related

- [Usage guide](usage.md)
- [Milestones](milestones.md)
- [Open-source boundary](open-source-boundary.md)
- [Privacy model](privacy.md)
- [Release and PR flow](release.md)
