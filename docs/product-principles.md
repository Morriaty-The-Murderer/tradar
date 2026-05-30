# Tradar Product Principles

This document records the product direction after v0.3. It is intentionally
about product judgment and architecture boundaries, not a task plan for a
single release.

## Positioning

Tradar is a vertical StartupAgent for builders who already work with agents.
Its job is to decide what is worth building next from real work traces, then
handoff the build to tools such as Codex, Claude Code, or another execution
agent.

Tradar should not be understood as a small utility that reads Codex and Claude
Code history files. The larger product is a trace consumption protocol and
opportunity judgment engine for AI-native builder workflows.

The product should move from reactive CLI commands toward proactive discovery:
weekly radar runs, post-session scans, and post-commit reflection. The long
term shape can be a desktop app, menu-bar app, or background daemon, but the
first durable interface is still the CLI.

## Product Principles

1. Tradar is not an idea generator.
   It only recommends opportunities grounded in real action evidence.

2. Tradar is not a coding agent.
   It decides what is worth building; Codex and Claude Code can build it.

3. Tradar is local-first and read-only by default.
   User work traces are private and must not be uploaded or exposed without
   explicit consent.

4. Every opportunity card must include evidence.
   No evidence, no recommendation.

5. Tradar optimizes for this week's demo, not long-term fantasy.
   The core output is a 48-hour demo brief.

6. Tradar must say no.
   It should identify noise, weak signals, and abandon signals.

7. Tradar should integrate with existing agents, not replace them.
   It should generate high-quality handoff prompts for Codex and Claude Code.

8. Tradar should become proactive.
   Its best mode is a weekly radar, post-session scan, or post-commit
   reflection, not waiting for the user to ask.

9. Tradar should define trace interfaces, not only adapters.
   Early versions can pull from external sources, but the long-term architecture
   should let tools push standard builder traces into Tradar.

## Input Strategy

Tradar needs both Pull and Push input modes, but they should not be equal in
the architecture.

Early product:

```bash
tradar scan codex
tradar scan claude
tradar scan git
tradar scan docs
tail -f agent.jsonl | tradar ingest
```

In this phase, Tradar owns the burden of adapting Codex sessions, Claude Code
sessions, git commit logs, and local docs. Pull adapters are useful because the
ecosystem will not adopt a Tradar format before the product proves useful.

Middle product:

```bash
tradar install codex-hook
tradar install obsidian-doc-mcp
```

In this phase, Tradar provides hook, SDK, and MCP entry points so other tools
can push trace events to Tradar without Tradar reverse-engineering every
history store.

Long-term product:

```typescript
import { trace } from "@tradar/trace";
```

```python
import tradar_trace
```

```rust
use tradar_trace as trace;
```

In this phase, Tradar defines a standard trace format for builder workflows.
The working name is Open Agent Trace Protocol. The name can change; the product
commitment should not. Tradar should become the consumer and validator of a
standard trace contract, not an endless collection of source-specific Pull
adapters.

This changes the core architecture: `tradar-core` should consume Push-shaped
trace envelopes. Pull connectors are edge producers that translate external
history into that same ingest interface.

## Agent-Native References

Tradar should learn from Codex and Claude Code because both products started
as coding agents and are becoming general local agent systems. The reference
point is not their coding domain, but their product architecture.

### Codex Patterns To Reference

- Shared core, multiple surfaces.
  Codex separates a local core agent from UI surfaces and protocol events.
  Tradar should mirror the boundary as `tradar-core`, with `tradar-cli`,
  future `tradar-ui`, scheduled runs, and any daemon using the same contracts.

- Event and session vocabulary.
  Codex's protocol model separates session, task, turn, operations, and
  events. Tradar needs a similar vocabulary for scan sessions, radar runs,
  opportunity cards, decisions, feedback events, and handoff artifacts.

- Local safety posture.
  Codex treats filesystem access, sandboxing, approvals, and commands as
  explicit runtime policy. Tradar's equivalent policy should be simpler and
  stricter: read-only by default, local evidence first, explicit consent
  before external analyst calls.

- Project guidance files.
  Codex uses layered project instruction files. Tradar should have a
  `TRADAR.md`, but it should record opportunity judgment preferences rather
  than generic agent instructions.

- Core discipline.
  Codex maintainers warn against letting `codex-core` absorb every new
  concern. Tradar should avoid making `tradar-core` a dumping ground: core
  owns contracts and deterministic judgment primitives, while UI, agent
  adapters, daemon scheduling, and connector-specific parsing stay outside
  unless they are truly shared.

### Claude Code Patterns To Reference

- Same engine across many surfaces.
  Claude Code presents terminal, IDE, desktop, web, CI, chat, and scheduled
  workflows as surfaces over the same underlying engine. Tradar should design
  the CLI as the first surface, not the whole product.

- Memory and project instructions.
  Claude Code separates user-written `CLAUDE.md` from automatically collected
  memory. Tradar should separate user-written `TRADAR.md` preferences from
  feedback-derived learning about which opportunities were accepted, built, or
  abandoned.

- Skills as packaged procedures.
  Claude Code skills turn repeatable procedures into discoverable commands.
  Tradar should eventually ship skills for Codex and Claude Code so agents can
  ask Tradar for a radar, request an opportunity brief, or generate a handoff
  prompt without bespoke integration code.

- Subagents for bounded context.
  Claude Code uses specialized subagents to keep exploration and execution
  from polluting the main conversation. Tradar can use this idea for analyst,
  skeptic, evidence-auditor, and handoff-writer roles, but those roles should
  operate on bounded evidence packs, not raw private traces.

- Hooks and external events.
  Claude Code hooks and MCP channels show how agent systems become proactive.
  Tradar's proactive mode should be local and conservative first: post-commit
  reflection, post-session scan, and weekly radar. The same idea should also
  shape the Push interface: hooks and MCP servers should emit trace envelopes,
  not require Tradar to parse every private history format forever.

### What Tradar Must Design Independently

- Opportunity judgment model.
  Coding agents optimize for task completion. Tradar optimizes for opportunity
  selection. Its scoring must reason about repeated evidence, user effort,
  demo feasibility, abandon signals, market pull, and whether the opportunity
  deserves a 48-hour build.

- Evidence contract.
  A recommendation is invalid without source IDs, snippets or summaries,
  confidence notes, and explicit warnings. This is the product's trust layer,
  not an implementation detail.

- Trace ingest contract.
  Tradar needs a stable event envelope for source identity, timestamps, actor,
  project, action, content summary, evidence references, privacy labels,
  idempotency keys, and schema version. This contract should be usable by
  `tradar ingest`, hooks, SDKs, MCP servers, and future daemon surfaces.

- User feedback loop.
  Tradar needs its own feedback flywheel:

  - Was the opportunity accepted?
  - Did the user really start a demo?
  - Was the demo finished?
  - Why was it abandoned?
  - Which scores were overestimated?
  - Which evidence was noise?
  - Which project types does the user repeatedly prefer?

- Negative recommendations.
  Tradar must be willing to suppress cards, downgrade confidence, and tell the
  user that an apparent signal is not worth building this week.

- Startup-agent handoff.
  Tradar should produce demo briefs and handoff prompts for execution agents,
  not try to become the execution agent.

## TRADAR.md

`TRADAR.md` should be a preference contract for opportunity judgment. It should
not become a long generic instruction file.

Good content:

- Preferred opportunity types.
- Domains the user understands or wants to avoid.
- Demo constraints such as available time, stack, budget, and distribution
  channels.
- Evidence the user trusts more or less.
- Repeated false positives and noisy signals.
- Abandon patterns from past attempts.
- Scoring corrections, for example "integration-heavy ideas are usually
  overestimated for weekend demos."
- Handoff preferences for Codex, Claude Code, or other agents.

Bad content:

- Generic agent etiquette.
- Coding style rules that belong in `AGENTS.md` or `CLAUDE.md`.
- Raw private traces.
- Aspirational product slogans that do not change opportunity ranking.

Future loading should probably support both user-level and project-level
preferences, but the first version can start with a single project-level
`TRADAR.md` discovered from the project root.

## tradar-core Boundary

`tradar-core` should be the stable service boundary underneath all future
interfaces.

Core owns:

- source registration and diagnostics;
- trace envelope, ingest API, validation, idempotency, and schema versioning;
- privacy and redaction policy execution;
- raw event and normalized evidence contracts;
- local evidence store access;
- evidence pack building and ranking;
- deterministic opportunity scoring primitives;
- opportunity card, demo brief, and warning schemas;
- decision and feedback event models;
- run artifact and audit metadata.

Core should not own:

- terminal presentation;
- desktop app layout;
- menu-bar scheduling UX;
- source-specific Pull adapter internals once they can be expressed as edge
  producers;
- Codex-specific or Claude-specific prompt text beyond typed adapter
  contracts;
- external uploads;
- daemon lifecycle management unless exposed behind a narrow scheduler
  interface.

## Prioritized Roadmap After v0.3

1. Product principles and `TRADAR.md` preference contract.
   This locks the product's judgment model before more interfaces are added.

2. `tradar-core` trace consumer boundary.
   Extract stable contracts so CLI, UI, daemon, agent integrations, and future
   Push producers all write into one ingest and evidence pipeline.

3. Push ingest interface.
   Define `tradar ingest`, the trace envelope schema, source identity,
   idempotency, privacy labels, and validation errors before adding many more
   Pull adapters.

4. Hook, SDK, and MCP producers.
   Add the first push producers, such as Codex hooks, Obsidian/Docs MCP, and
   library packages that can emit standard builder traces.

5. Agent integration and handoff skills.
   Add first-class handoff prompts and package Tradar usage as Codex and Claude
   Code skills.

6. User feedback loop.
   Record accepted, rejected, started, completed, and abandoned opportunities,
   then feed those outcomes back into later ranking.

7. Proactive local runs.
   Add weekly radar, post-session scan, and post-commit reflection once the
   feedback model can keep proactive suggestions from becoming noise.

8. Desktop, menu-bar, or daemon surface.
   Build the always-on product shell only after the core loop proves it can say
   useful things without being asked.

9. Open Agent Trace Protocol.
   If the Push interface proves useful, publish language SDKs and a stable
   trace spec so external builder tools can conform to Tradar's trace contract.

10. Team workflows.
   Defer team mode until the single-builder evidence loop is clearly useful.

## Research References

- [OpenAI Codex repository](https://github.com/openai/codex)
- [OpenAI Codex protocol notes](https://github.com/openai/codex/blob/main/codex-rs/docs/protocol_v1.md)
- [OpenAI AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)
- [Claude Code overview](https://docs.anthropic.com/en/docs/claude-code/overview)
- [Claude Code memory and CLAUDE.md](https://docs.anthropic.com/en/docs/claude-code/memory)
- [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills)
- [Claude Code subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents)
- [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [Claude Code MCP](https://docs.anthropic.com/en/docs/claude-code/mcp)
