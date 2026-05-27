from __future__ import annotations

from tradar.renderer.base import render_base_report, validate_required_sections
from tradar.schemas import (
    CredibleSuccessPath,
    DecisionPrompt,
    DemoBrief,
    OpportunityCard,
    PrototypePanel,
    RadarReport,
    RunSummary,
    SearchTrace,
    ThisWeeksDemo,
)


def _report() -> RadarReport:
    card = OpportunityCard(
        title="Agent Workflow Radar",
        one_sentence="Find project ideas from real agent work evidence.",
        evidence_ids=["ev_1", "ev_2"],
        evidence_notes=["Codex sessions repeat this theme.", "Docs already specify it."],
        why_you=["You already preserve agent work as evidence."],
        why_now=["Recent Codex and Claude Code sessions are enough for a first report."],
        first_users="Personal builders using local coding agents.",
        demo_48h=["Scan sources.", "Build pack.", "Render report."],
        adjacent_products=["Activity dashboards: weaker opportunity framing."],
        search_trace=SearchTrace(used_search=False, impact="none"),
        risks=["Could become a generic summary."],
        kill_signals=["No card makes the user start a demo."],
        demo_brief=DemoBrief(
            one_screen_product_shape="Run summary, top demo, and cards.",
            core_interaction="Copy Start or Skip command.",
            data_needed=["Codex sessions", "Claude Code sessions"],
            prototype_panel=PrototypePanel(
                one_screen_mock="Top memo layout.",
                core_interaction_state="Command block highlighted.",
                empty_state="Show source doctor CTAs.",
                success_state="Accepted demo is visible.",
                data_placeholders=["run_id", "card_id"],
            ),
            prototype_prompt="Build a dense local HTML memo.",
            boundary_48h="No desktop shell.",
            demo_success_signal="User starts one demo.",
            demo_kill_signal="Cards are generic.",
        ),
        credible_success_path=CredibleSuccessPath(
            narrow_user="Personal builder.",
            current_alternative="Manual rereading.",
            credible_demand_evidence="Repeated local agent sessions.",
            first_distribution_path="Private dogfood.",
            two_week_validation_signal="One accepted demo.",
            kill_signal="No evidence-backed recommendation.",
        ),
    )
    return RadarReport(
        run_summary=RunSummary(
            run_id="run_demo",
            generated_at="2026-05-24T08:00:00Z",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=12,
            warning_count=1,
            rendered_by="base",
            debug_bundle_path="/tmp/tradar/runs/run_demo",
        ),
        opportunity_cards=[card],
        this_weeks_demo=ThisWeeksDemo(
            card_id=card.card_id,
            title=card.title,
            summary=card.one_sentence,
            evidence_strength="high",
            start_command="tradar accept " + card.card_id,
            skip_command="tradar reject " + card.card_id,
        ),
        decision_prompt=DecisionPrompt(
            suggested_start_card_id=card.card_id,
            start_command="tradar accept " + card.card_id,
            snooze_command="tradar snooze " + card.card_id,
            reject_command="tradar reject " + card.card_id,
            needs_user_confirmation=["Confirm whether to start this demo."],
        ),
    )


def test_base_renderer_outputs_required_sections_and_privacy_notice() -> None:
    html = render_base_report(_report())

    assert validate_required_sections(html) == []
    assert "Run Summary" in html
    assert "This Week's Demo" in html
    assert "Project Opportunity Cards" in html
    assert "Demo Briefs" in html
    assert "Decision Prompt" in html
    assert "本报告基于本地数据生成，未做完整脱敏" in html
    assert "tradar accept" in html
    assert "rendered_by: base" in html
    assert "/tmp/tradar/runs/run_demo" in html
    for artifact in [
        "run.json",
        "warnings.jsonl",
        "evidence_pack.json",
        "agent_raw_output.json",
        "validated_report.json",
        "render.log",
        "report.html",
    ]:
        assert f'href="{artifact}"' in html


def test_required_section_validator_reports_missing_sections() -> None:
    missing = validate_required_sections("<html><body>Run Summary</body></html>")

    assert missing == [
        "This Week's Demo",
        "Project Opportunity Cards",
        "Demo Briefs",
        "Decision Prompt",
    ]
