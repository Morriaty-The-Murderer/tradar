from __future__ import annotations

import json

import pytest

from tradar.agent_runner.schema_repair import (
    AgentOutputSchemaError,
    FixedSchemaRepairAdapter,
    validate_or_repair_report,
)


def _valid_report_json() -> str:
    card = {
        "title": "Agent Workflow Radar",
        "one_sentence": "Find project ideas from real agent work evidence.",
        "evidence_ids": ["ev_1", "ev_2"],
        "evidence_notes": ["Codex repeats this.", "Docs specify it."],
        "why_you": ["The user already preserves agent work."],
        "why_now": ["Recent sessions are enough."],
        "first_users": "Personal builders.",
        "demo_48h": ["Scan.", "Pack.", "Render."],
        "adjacent_products": [],
        "search_trace": {"used_search": False, "impact": "none"},
        "risks": ["Generic summaries."],
        "kill_signals": ["No accepted demo."],
    }
    report = {
        "run_summary": {
            "run_id": "run_agent",
            "generated_at": "2026-05-24T08:00:00Z",
            "timezone": "Asia/Shanghai",
            "days_window": 30,
            "evidence_count": 2,
            "warning_count": 0,
            "rendered_by": "base",
        },
        "opportunity_cards": [card],
        "decision_prompt": {
            "suggested_start_card_id": None,
            "needs_user_confirmation": ["Confirm demo start."],
        },
    }
    return json.dumps(report)


def test_validate_or_repair_report_uses_repair_once_for_missing_required_section() -> None:
    broken = json.loads(_valid_report_json())
    broken.pop("decision_prompt")
    repaired = json.loads(_valid_report_json())
    adapter = FixedSchemaRepairAdapter(json.dumps(repaired))

    report = validate_or_repair_report(json.dumps(broken), adapter)

    assert adapter.calls == 1
    assert [card.title for card in report.opportunity_cards] == ["Agent Workflow Radar"]
    assert report.opportunity_cards[0].evidence_ids == ["ev_1", "ev_2"]


def test_schema_repair_rejects_changed_ranking_or_new_evidence() -> None:
    broken = json.loads(_valid_report_json())
    broken.pop("decision_prompt")
    changed = json.loads(_valid_report_json())
    changed["opportunity_cards"][0]["evidence_ids"] = ["ev_1", "ev_new"]
    adapter = FixedSchemaRepairAdapter(json.dumps(changed))

    with pytest.raises(AgentOutputSchemaError):
        validate_or_repair_report(json.dumps(broken), adapter)


def test_schema_repair_preserves_ranking_by_card_id_when_title_was_missing() -> None:
    broken = json.loads(_valid_report_json())
    broken["opportunity_cards"][0].pop("title")
    broken.pop("decision_prompt")
    repaired = json.loads(_valid_report_json())
    adapter = FixedSchemaRepairAdapter(json.dumps(repaired))

    report = validate_or_repair_report(json.dumps(broken), adapter)

    assert report.opportunity_cards[0].title == "Agent Workflow Radar"


def test_schema_repair_fails_fast_after_one_failed_repair() -> None:
    broken = json.loads(_valid_report_json())
    broken.pop("decision_prompt")
    adapter = FixedSchemaRepairAdapter("{not valid json")

    with pytest.raises(AgentOutputSchemaError):
        validate_or_repair_report(json.dumps(broken), adapter)

    assert adapter.calls == 1
