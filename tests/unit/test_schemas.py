from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tradar.schemas import (
    CredibleSuccessPath,
    DecisionPrompt,
    DecisionState,
    DemoBrief,
    OpportunityCard,
    PrototypePanel,
    RadarReport,
    RawEvent,
    RunSummary,
    SearchTrace,
    ThisWeeksDemo,
)


def test_raw_event_normalizes_event_time_to_utc_and_falls_back_to_captured_at() -> None:
    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/tmp/session.jsonl",
        captured_at="2026-05-24T15:00:00+08:00",
        title="Build radar",
        raw_text="User asked the agent to build a radar.",
    )

    assert event.captured_at == datetime(2026, 5, 24, 7, 0, tzinfo=UTC)
    assert event.event_time == event.captured_at


def test_raw_event_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError):
        RawEvent(
            source_type="codex_session",
            source_id="session-1",
            source_path="/tmp/session.jsonl",
            captured_at=datetime(2026, 5, 24, 15, 0),
            title="Build radar",
            raw_text="User asked the agent to build a radar.",
        )


def test_radar_report_requires_demo_to_reference_existing_card() -> None:
    card = OpportunityCard(
        title="Agent Workflow Radar",
        one_sentence="Find project ideas from real agent work evidence.",
        evidence_ids=["ev_1", "ev_2"],
        evidence_notes=["Codex sessions repeat this theme.", "Project docs already specify it."],
        why_you=["The user already works through agent sessions."],
        why_now=["Recent sessions contain enough source material."],
        first_users="Personal builder using local coding agents.",
        demo_48h=["Read sources.", "Build evidence pack.", "Render HTML report."],
        adjacent_products=["Activity report tools: less project-opportunity focused."],
        search_trace=SearchTrace(used_search=False, impact="none"),
        risks=["May become a generic summary report."],
        kill_signals=["No card makes the user want to start a 48h demo."],
        demo_brief=DemoBrief(
            one_screen_product_shape="A dense weekly decision memo.",
            core_interaction="Pick Start or Skip by copying a local command.",
            data_needed=["Codex sessions", "Claude Code sessions", "project docs"],
            prototype_panel=PrototypePanel(
                one_screen_mock="Run summary, top demo, and first card teaser.",
                core_interaction_state="Command block is highlighted for copy.",
                empty_state="Show source doctor CTAs.",
                success_state="Show one accepted demo candidate.",
                data_placeholders=["card_id", "evidence_count", "run_id"],
            ),
            prototype_prompt="Build a local HTML report for Tradar.",
            boundary_48h="No desktop shell, no watcher, no cloud sync.",
            demo_success_signal="The user wants to start one demo.",
            demo_kill_signal="Cards read like generic startup ideas.",
        ),
        credible_success_path=CredibleSuccessPath(
            narrow_user="A personal builder using Codex and Claude Code.",
            current_alternative="Manually rereading notes and commits.",
            credible_demand_evidence="Repeated agent sessions and docs mention project selection.",
            first_distribution_path="Use it privately, then share a redacted report.",
            two_week_validation_signal="It produces one accepted demo in two weeks.",
            kill_signal="It cannot cite evidence for recommendations.",
        ),
    )

    report = RadarReport(
        run_summary=RunSummary(
            run_id="run_20260524",
            generated_at="2026-05-24T15:30:00+08:00",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=42,
            warning_count=1,
            rendered_by="base",
        ),
        opportunity_cards=[card],
        this_weeks_demo=ThisWeeksDemo(
            card_id=card.card_id,
            title=card.title,
            summary=card.one_sentence,
            evidence_strength="high",
            start_command=f"tradar accept {card.card_id}",
            skip_command=f"tradar reject {card.card_id}",
        ),
        decision_prompt=DecisionPrompt(
            suggested_start_card_id=card.card_id,
            start_command=f"tradar accept {card.card_id}",
            snooze_command=f"tradar snooze {card.card_id}",
            reject_command=f"tradar reject {card.card_id}",
            needs_user_confirmation=["Confirm whether to start the 48h demo."],
        ),
    )

    assert report.this_weeks_demo.card_id == card.card_id
    assert card.card_id.startswith("card_")

    with pytest.raises(ValidationError):
        RadarReport(
            run_summary=report.run_summary,
            opportunity_cards=[card],
            this_weeks_demo=ThisWeeksDemo(
                card_id="card_missing",
                title="Missing",
                summary="Should fail.",
                evidence_strength="low",
                start_command="tradar accept card_missing",
                skip_command="tradar reject card_missing",
            ),
            decision_prompt=report.decision_prompt,
        )


def test_opportunity_card_requires_at_least_two_evidence_ids() -> None:
    with pytest.raises(ValidationError, match="at least two evidence"):
        OpportunityCard(
            title="Thin Signal",
            one_sentence="A card with only one evidence item is too weak for a project decision.",
            evidence_ids=["ev_1"],
            evidence_notes=["Only one isolated signal."],
            why_you=["The user mentioned it once."],
            why_now=["It appeared recently."],
            first_users="Solo builder.",
            demo_48h=["Sketch a mock."],
            risks=["May be a one-off."],
            kill_signals=["No second supporting signal appears."],
        )


def test_decision_state_uses_utc_timestamp_and_known_decisions() -> None:
    state = DecisionState(card_id="card_demo", decision="accept")

    assert state.decided_at.tzinfo == UTC

    with pytest.raises(ValidationError):
        DecisionState(card_id="card_demo", decision="maybe")


def test_run_summary_accepts_known_report_status_and_next_steps() -> None:
    summary = RunSummary(
        run_id="run_partial",
        generated_at="2026-05-24T15:30:00+08:00",
        timezone="Asia/Shanghai",
        days_window=30,
        evidence_count=3,
        warning_count=1,
        rendered_by="base",
        report_status="partial",
        next_steps=["uv run python -m tradar.cli.app scan"],
    )

    assert summary.report_status == "partial"
    assert summary.next_steps == ["uv run python -m tradar.cli.app scan"]

    with pytest.raises(ValidationError):
        RunSummary(
            run_id="run_bad",
            generated_at="2026-05-24T15:30:00+08:00",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=3,
            warning_count=1,
            rendered_by="base",
            report_status="stale",
        )
