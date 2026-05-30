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

## Later

- Desktop shell or menu-bar wrapper around the CLI.
- Scheduled local runs.
- Additional agent trace connectors.
- Optional team workflows, if the single-builder loop proves useful first.
