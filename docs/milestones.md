# Tradar Milestones

This file describes the public roadmap at a level suitable for contributors. Internal task plans, local source-discovery notes, and real machine sampling results are kept outside the public branch.

## v0.1: Local CLI Engine

Status: implemented in the current source checkout.

- Parse Codex, Claude Code, project docs, and git commit subjects.
- Normalize evidence into a local SQLite store.
- Build bounded evidence packs.
- Generate deterministic base HTML reports.
- Optionally call a Codex analyst adapter.
- Optionally call an enhanced HTML design adapter.
- Preserve debug bundles for traceability.
- Support local decisions with `accept`, `snooze`, and `reject`.

## v0.2: Packaging And First Public Use

Status: implemented in the current source checkout.

- Package and install cleanly as `tradar`.
- Add release automation with PyPI trusted publishing after the public repository is established.
- Expand example configs and sanitized fixture coverage.
- Improve CLI onboarding and first-run diagnostics.
- Document privacy controls in more detail.
- Configure Codex and Claude Code CLI binaries for agent-backed report modes.

## v0.3: Better Signal Quality

Status: implemented in the current source checkout.

- Deduplicate noisy repeated signals across agent traces before analyst packing.
- Add default secret redaction and configurable local redaction policy hooks.
- Rank packed evidence by recurrence, confidence, recency, and stable ID.
- Add Run Summary confidence notes for pack coverage, omitted evidence, and
  duplicate signals.
- Add more connector fixtures from sanitized public Codex and Claude examples.
- Keep enhanced HTML focused on preserving confidence, warnings, required
  report sections, and interactive Demo Brief previews.

## v0.4: Product Judgment Preferences

Status: planned.

- Publish the product principles that keep Tradar focused on evidence-backed
  opportunity judgment instead of generic idea generation.
- Introduce `TRADAR.md` as a user-owned opportunity preference contract.
- Load project-level `TRADAR.md` into ranking and report generation without
  treating it as untrusted evidence.
- Add schema-covered examples for preference fields such as trusted evidence,
  no-go domains, demo constraints, and historical false positives.
- Keep `AGENTS.md` and `CLAUDE.md` focused on agent behavior; keep
  `TRADAR.md` focused on opportunity judgment.

## v0.5: tradar-core Trace Consumer Boundary

Status: planned.

- Separate a stable `tradar-core` boundary from the Typer CLI surface.
- Make `tradar-core` consume a Push-shaped trace envelope, even when the first
  sources are still pulled from Codex sessions, Claude Code sessions, git, and
  docs.
- Make source diagnostics, trace ingest, privacy policy, evidence
  normalization, packing, scoring, decisions, feedback events, and run artifacts
  available through typed core APIs.
- Keep UI presentation, agent prompts, scheduled execution, and daemon
  lifecycle outside core unless they need a narrow shared interface.
- Add contract tests so `tradar-cli`, future `tradar-ui`, and daemon workflows
  use the same evidence and report semantics.

## v0.6: Push Ingest Interface

Status: planned.

- Define the first public trace envelope for AI-native builder workflows.
- Add `tradar ingest` so sources can push newline-delimited trace events through
  stdin or file input.
- Include schema version, source identity, project identity, actor, timestamp,
  action type, evidence summary, privacy labels, and idempotency keys.
- Keep Pull connectors as edge producers that translate external history into
  the same ingest interface.
- Document validation errors so external tools can conform without knowing
  Tradar internals.

## v0.7: Hooks, SDK, And MCP Producers

Status: planned.

- Provide first push producers such as `tradar install codex-hook` and
  `tradar install obsidian-doc-mcp`.
- Define the installer shape for hooks and MCP servers without requiring every
  source integration to be fully implemented in the same release.
- Prototype language packages such as `@tradar/trace`, `tradar-trace-py`, and
  `tradar-trace-rs` once the ingest envelope is stable enough.
- Keep all producers local-first and explicit about whether any external
  service is contacted.

## v0.8: Agent Handoff And Skills

Status: planned.

- Generate high-quality handoff prompts for Codex and Claude Code from each
  opportunity card and 48-hour demo brief.
- Add a first Tradar skill package so existing agents can request a radar,
  inspect a brief, or ask for a handoff prompt without bespoke glue code.
- Keep Tradar in the "decide what is worth building" role, while execution
  agents remain responsible for implementation.
- Add fixtures for handoff prompt stability and evidence citation integrity.

## v0.9: User Feedback Loop

Status: planned.

- Record whether a card was accepted, rejected, snoozed, converted into a demo,
  completed, or abandoned.
- Capture abandon reasons, score overestimation, noisy evidence, and preferred
  project types as local feedback events.
- Feed feedback into later ranking while preserving auditability of every
  scoring adjustment.
- Add report sections that explain why Tradar changed its confidence after
  prior user outcomes.

## v0.10: Proactive Local Runs

Status: planned.

- Add opt-in weekly radar runs, post-session scans, and post-commit reflection.
- Keep proactive mode local-first, read-only by default, and explicit about
  whether any external analyst adapter will be called.
- Add noise controls so proactive runs can say "nothing worth building this
  week" instead of forcing weak cards into the report.
- Store proactive run artifacts with the same traceability as manual runs.

## v0.11: Desktop Or Menu-Bar Shell

Status: planned.

- Wrap the proven core loop in a desktop, menu-bar, or background daemon
  surface.
- Show current radar status, new signals, pending demo briefs, and feedback
  prompts without requiring a manual CLI run.
- Keep all private work traces local unless the user explicitly exports or
  shares a report.

## v1.0: Open Agent Trace Protocol

Status: planned.

- Publish a stable builder trace specification once the Push ingest interface
  has proven useful in real workflows.
- Treat Open Agent Trace Protocol as a working name until the standard's scope
  is clearer.
- Define conformance rules for external producers, including required fields,
  privacy labels, source identity, evidence references, and versioning.
- Keep Tradar as the opportunity judgment engine that consumes the protocol,
  not just a collection of one-off Pull adapters.

## Later

- Additional Pull connectors where no Push producer exists yet.
- Optional team workflows, if the single-builder loop proves useful first.
