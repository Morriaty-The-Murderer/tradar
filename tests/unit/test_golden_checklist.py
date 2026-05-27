from __future__ import annotations

from tradar.evidence.pack_builder import EvidencePack, EvidencePackItem, OmittedSummary
from tradar.golden.checklist import evaluate_golden_report
from tradar.schemas import (
    CredibleSuccessPath,
    DecisionPrompt,
    DemoBrief,
    OpportunityCard,
    PrototypePanel,
    RadarReport,
    RunSummary,
    ThisWeeksDemo,
    generate_card_id,
)
from tradar.schemas.time import ensure_utc_datetime


def test_golden_checklist_accepts_traceable_report() -> None:
    report = _report(card=_card(evidence_ids=["ev_1", "ev_2"]))
    pack = _pack(["ev_1", "ev_2"])

    result = evaluate_golden_report(report, pack)

    assert result.passed
    assert result.failures == []
    assert "manual.user_wants_48h_demo" in result.manual_checks


def test_golden_checklist_reports_structural_quality_gaps() -> None:
    card = _card(evidence_ids=["ev_1", "ev_2"], with_demo_brief=False, with_success_path=False)
    report = _report(
        card=card,
        with_demo=False,
        with_sources=False,
        with_prompt_assets=False,
        with_confidence_note=False,
        with_should_not_do=False,
    )
    pack = _pack(["ev_1", "ev_2"])

    result = evaluate_golden_report(report, pack)

    assert not result.passed
    card_id = card.card_id
    assert f"card.{card_id}.demo_brief_missing" in result.failures
    assert f"card.{card_id}.credible_success_path_missing" in result.failures
    assert "this_weeks_demo.missing" in result.failures
    assert "run_summary.sources_missing" in result.failures
    assert "run_summary.prompt_assets_missing" in result.failures
    assert "run_summary.confidence_note_missing" in result.failures
    assert "decision_prompt.should_not_do_missing" in result.failures


def test_golden_checklist_rejects_unknown_evidence_ids() -> None:
    report = _report(card=_card(evidence_ids=["ev_1", "ev_missing"]))
    pack = _pack(["ev_1", "ev_2"])

    result = evaluate_golden_report(report, pack)

    assert not result.passed
    expected_failure = (
        f"card.{report.opportunity_cards[0].card_id}.unknown_evidence_id.ev_missing"
    )
    assert expected_failure in result.failures


def _report(
    card: OpportunityCard,
    with_demo: bool = True,
    with_sources: bool = True,
    with_prompt_assets: bool = True,
    with_confidence_note: bool = True,
    with_should_not_do: bool = True,
) -> RadarReport:
    config_overrides = {}
    if with_prompt_assets:
        config_overrides = {
            "analyst_prompt_hash": "a" * 64,
            "schema_repair_prompt_hash": "b" * 64,
            "html_design_prompt_hash": "c" * 64,
        }
    return RadarReport(
        run_summary=RunSummary(
            run_id="run_golden",
            generated_at="2026-05-24T08:00:00Z",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=2,
            warning_count=0,
            rendered_by="base",
            config_overrides=config_overrides,
            sources_requested=["codex_session", "project_docs"] if with_sources else [],
            sources_succeeded=["codex_session", "project_docs"] if with_sources else [],
            debug_bundle_path="/tmp/tradar/run_golden",
            confidence_note="The report is based on repeated local evidence."
            if with_confidence_note
            else None,
        ),
        opportunity_cards=[card],
        this_weeks_demo=ThisWeeksDemo(
            card_id=card.card_id,
            title=card.title,
            summary="Start this demo first.",
            evidence_strength="medium",
            start_command="tradar accept card_demo",
            skip_command="tradar snooze card_demo",
        )
        if with_demo
        else None,
        decision_prompt=DecisionPrompt(
            should_not_do=["暂不做泛化团队版。"] if with_should_not_do else [],
            needs_user_confirmation=["确认是否启动 48 小时 demo。"],
        ),
    )


def _card(
    evidence_ids: list[str],
    with_demo_brief: bool = True,
    with_success_path: bool = True,
) -> OpportunityCard:
    return OpportunityCard(
        title="Tradar Agent Path",
        card_id=generate_card_id("Tradar Agent Path", evidence_ids),
        one_sentence="Turn local agent evidence into project opportunity cards.",
        evidence_ids=evidence_ids,
        evidence_notes=["Codex work repeats this.", "Project docs specify it."],
        why_you=["The user already works through local agent traces."],
        why_now=["The evidence store and renderer are already implemented."],
        first_users="Solo builders using local coding agents.",
        demo_48h=["Scan.", "Generate.", "Review."],
        risks=["Agent output may become generic."],
        kill_signals=["No card is accepted after review."],
        demo_brief=_demo_brief() if with_demo_brief else None,
        credible_success_path=_success_path() if with_success_path else None,
    )


def _demo_brief() -> DemoBrief:
    return DemoBrief(
        one_screen_product_shape="A weekly report with cards and evidence.",
        core_interaction="Accept, snooze, or reject one project card.",
        data_needed=["Codex sessions", "Project docs"],
        prototype_panel=PrototypePanel(
            one_screen_mock="Left evidence rail, right opportunity card.",
            core_interaction_state="A selected card shows evidence citations.",
            empty_state="No high-confidence opportunity yet.",
            success_state="One 48 hour demo is accepted.",
            data_placeholders=["session title", "evidence id"],
        ),
        prototype_prompt="Build one screen for reviewing project cards.",
        boundary_48h="No desktop app or watcher.",
        demo_success_signal="User accepts one project card.",
        demo_kill_signal="All cards feel generic.",
    )


def _success_path() -> CredibleSuccessPath:
    return CredibleSuccessPath(
        narrow_user="Solo builders using local coding agents.",
        current_alternative="Manual notes and scattered session search.",
        credible_demand_evidence="Repeated local evidence already exists.",
        first_distribution_path="Share a local-first CLI demo.",
        two_week_validation_signal="Three users accept one generated project card.",
        kill_signal="Users do not trust the evidence chain.",
    )


def _pack(evidence_ids: list[str]) -> EvidencePack:
    return EvidencePack(
        items=[
            EvidencePackItem(
                evidence_id=evidence_id,
                source_type="codex_session",
                source_ref="session-1",
                title="Evidence " + evidence_id,
                summary="Repeated work on project radar.",
                raw_excerpt="Build Tradar.",
                observed_at=ensure_utc_datetime("2026-05-24T08:00:00Z"),
                recurrence_count=1,
                confidence=1.0,
            )
            for evidence_id in evidence_ids
        ],
        omitted_summary=OmittedSummary(total_omitted=0),
    )
