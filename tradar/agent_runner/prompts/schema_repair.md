# Tradar Schema Repair Prompt

Repair the provided JSON so it matches the `RadarReport` schema.

Do not add new evidence.
Do not change ranking.
Do not change recommendations.
Only fix missing or invalid fields using existing content.
Return only repaired JSON.

Required repair rules:

- `run_summary.rendered_by` must be `"base"` or `"enhanced"`; use `"base"` when missing or invalid.
- `run_summary.generated_at` must be a timezone-aware ISO datetime string; add `Z` when
  a timestamp is otherwise valid but timezone-free.
- `run_summary.days_window` must be an integer; convert numeric strings to integers.
- If an opportunity card is missing `title`, derive a concise title from its
  `one_sentence` without changing card order.
- Convert scalar strings to one-item lists when the schema expects a list, including
  `evidence_notes`, `why_you`, `why_now`, and `demo_brief.data_needed`.
- Rename `required_data` to `data_needed`.
- `demo_brief.prototype_panel` must be an object with `one_screen_mock`,
  `core_interaction_state`, `empty_state`, `success_state`, and
  `data_placeholders`; expand a string summary into those fields.
- The `prototype_panel` and `one_screen_mock` names are legacy schema names.
  When expanding or repairing them, preserve the source meaning but phrase the
  content as a high-fidelity product UI screen, not a wireframe, placeholder
  skeleton, box-and-line mock, or low-fidelity prototype.
- `demo_brief.boundary_48h` must be a single string; join list items into one concise string.
- Rename `success_signal` to `demo_success_signal`.
- Rename `demo_brief.kill_signal` to `demo_kill_signal`.
- Rename `demand_evidence` to `credible_demand_evidence`.
- Keep `credible_success_path.kill_signal` as `credible_success_path.kill_signal`; do not
  rename it to `demo_kill_signal`.
