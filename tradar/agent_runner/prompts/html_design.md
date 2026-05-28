# Tradar HTML Design Prompt

Improve an existing base HTML Tradar report into a high-density product
decision memo plus high-fidelity product UI preview. Use Open Design's
web-prototype discipline to compose a single self-contained HTML file, keep
semantic sections targetable, prefer native HTML, maintain accessible contrast
and focus states, and use a small refined token set instead of decorative
effects.

Before redesigning, call the local Open Design daemon when it is available:

```bash
curl -s http://127.0.0.1:7456/api/health
curl -s http://127.0.0.1:7456/api/mcp/install-info
curl -s http://127.0.0.1:7456/api/agents
curl -s http://127.0.0.1:7456/api/skills
curl -s http://127.0.0.1:7456/api/design-systems
```

Use the returned Open Design capabilities as design input. If the skills or
design-system registry is empty, still follow the Open Design packaged
`web-prototype` skill principles and the refined/application design-system
style: strong hierarchy, compact responsive grids, restrained surface treatment,
clear interaction states, and accessible UI primitives. Do not block the render
only because Open Design has an empty registry; treat it as a design guide and
continue.

The visual direction is restrained and operational: crisp neutral surfaces,
blue action emphasis, compact grids, clear command blocks, and polished
high-fidelity UI screens that make the next 48-hour demo understandable at a
glance. This is not a marketing page, landing page, generic analytics
dashboard, wireframe, skeleton mock, or low-fidelity sketch.

Multilingual support is required:

- Preserve Chinese and English UI labels in the final HTML.
- Include a visible language switcher for `中文` and `English`.
- The default language should be Chinese, while English labels must be available
  in the DOM and switchable without a build step.
- Do not translate evidence text, commands, IDs, file paths, or user-provided
  content unless the source already provides that language. Translate only the
  report chrome, section labels, empty states, and control labels.

Preserve all required sections exactly:

- Run Summary
- This Week's Demo
- Project Opportunity Cards
- Demo Briefs
- Decision Prompt

Required behavior:

- Keep card order unchanged.
- Do not add unsupported facts, invented metrics, external claims, or new
  recommendations.
- Do not delete, rename, or hide command blocks. They are copyable local CLI
  actions, not fake buttons.
- Keep the privacy notice visible near the top.
- Preserve the Demo Brief `prototype_panel` data, but render it as a polished
  high-fidelity product UI screen. Do not draw a wireframe, blueprint grid,
  low-fidelity mockup, placeholder skeleton, or box-and-line prototype.
- The Demo Brief UI should look like a real application screen: app chrome,
  navigation, toolbar, dense data rows or panels, real state chips, action
  affordances, empty and success states, and believable spacing/colors.
- If you use the source fields `one_screen_mock` or `prototype_prompt`, relabel
  them visually as high-fidelity screen / hi-fi generation prompt, not as mock
  or wireframe language.
- Preserve local debug artifact links when present.
- Keep the first viewport answerable: what to do this week, why, evidence
  strength, risk/confidence, and the next local command.
- Use headings and landmarks in DOM order; do not rely on visual styling to fake
  structure.

Design constraints:

- Use a compact two-column desktop layout that collapses to one column under
  roughly 920px.
- Keep cards at 8px radius or less.
- Avoid nested cards; use panels, grids, lists, and small metric cells.
- Use one primary accent at a time. Warnings, danger, and success may use
  separate semantic colors only when they clarify state.
- Do not use decorative gradient blobs, stock images, oversized hero marketing
  copy, or fake controls.
- Ensure long commands and IDs wrap without overflowing their container.

Return only the final complete HTML. No Markdown explanation.
