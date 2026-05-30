# Tradar Architecture

Tradar is a local-first CLI for turning agent work traces into evidence-backed
project signals. The long-term architecture is a trace consumer protocol and
opportunity judgment engine: Pull connectors are compatibility adapters, while
`tradar-core` should consume a common Push-shaped trace envelope.

## Pipeline

```text
Codex sessions
Claude Code sessions
Project docs
Git commit subjects
        |
        v
Pull connectors
        |                       Push producers
        |                       hooks / SDKs / MCP / tradar ingest
        |                       |
        v                       v
        +---------------------> TraceEnvelope
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

## Input Model

The first product phase is Pull-oriented because Tradar must adapt existing
sources before the ecosystem knows its format. The core boundary should still
be Push-oriented:

- Pull connectors read Codex sessions, Claude Code sessions, git history, and
  local docs, then emit trace envelopes.
- `tradar ingest` accepts trace envelopes from stdin or files.
- Future hooks, SDKs, and MCP servers push the same trace envelopes directly.
- `tradar-core` validates source identity, schema version, idempotency, privacy
  labels, and evidence payload shape before normalization.

This keeps source-specific parsing at the edge and prevents every future
interface from inventing a separate ingestion path.

## Core Boundaries

- Pull connectors read local evidence and emit trace envelopes through the same
  ingest boundary used by Push producers.
- Push producers use `tradar ingest`, hooks, SDKs, or MCP servers to send trace
  envelopes without requiring Tradar to parse their private history stores.
- The privacy gate applies default secret redaction and optional local
  redaction policy hooks before events are normalized.
- The normalizer converts accepted trace events into evidence records.
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
- [Product principles](product-principles.md)
- [Milestones](milestones.md)
- [Open-source boundary](open-source-boundary.md)
- [Privacy model](privacy.md)
- [Release and PR flow](release.md)
