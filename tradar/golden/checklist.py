"""Golden report checklist。

这里不评价创意质量，只做可自动判断的结构和证据链检查。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tradar.evidence.pack_builder import EvidencePack, EvidencePackItem, OmittedSummary
from tradar.schemas import DemoBrief, RadarReport, generate_card_id
from tradar.schemas.time import ensure_utc_datetime


@dataclass(frozen=True)
class GoldenChecklistResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    manual_checks: list[str] = field(default_factory=list)


def evaluate_golden_report(
    report: RadarReport,
    evidence_pack: EvidencePack | None = None,
) -> GoldenChecklistResult:
    failures: list[str] = []
    known_evidence_ids = (
        {item.evidence_id for item in evidence_pack.items} if evidence_pack is not None else None
    )

    if report.this_weeks_demo is None:
        failures.append("this_weeks_demo.missing")

    if not report.run_summary.sources_requested or not report.run_summary.sources_succeeded:
        failures.append("run_summary.sources_missing")

    if not _has_prompt_assets(report):
        failures.append("run_summary.prompt_assets_missing")

    if not report.run_summary.confidence_note:
        failures.append("run_summary.confidence_note_missing")

    if not report.decision_prompt.should_not_do:
        failures.append("decision_prompt.should_not_do_missing")

    for card in report.opportunity_cards:
        card_ref = card.card_id or card.title
        if card.card_id != generate_card_id(card.title, card.evidence_ids):
            failures.append(f"card.{card_ref}.system_card_id_mismatch")
        if len(card.evidence_ids) < 2:
            failures.append(f"card.{card_ref}.min_evidence")
        if known_evidence_ids is not None:
            for evidence_id in card.evidence_ids:
                if evidence_id not in known_evidence_ids:
                    failures.append(f"card.{card_ref}.unknown_evidence_id.{evidence_id}")
        if card.demo_brief is None:
            failures.append(f"card.{card_ref}.demo_brief_missing")
        elif _missing_demo_brief_fields(card.demo_brief):
            failures.append(f"card.{card_ref}.demo_brief_incomplete")
        if card.credible_success_path is None:
            failures.append(f"card.{card_ref}.credible_success_path_missing")
        if not card.kill_signals:
            failures.append(f"card.{card_ref}.kill_signal_missing")

    return GoldenChecklistResult(
        passed=not failures,
        failures=failures,
        manual_checks=[
            "manual.user_wants_48h_demo",
            "manual.success_path_from_evidence_not_business_plan",
            "manual.no_unsupported_project_judgment",
        ],
    )


def load_evidence_pack(path: Path) -> EvidencePack:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence pack must be a JSON object")

    items = raw.get("items") or []
    if not isinstance(items, list):
        raise ValueError("evidence pack items must be a list")

    omitted = raw.get("omitted_summary") or {}
    if not isinstance(omitted, dict):
        omitted = {}

    return EvidencePack(
        items=[_pack_item(item) for item in items if isinstance(item, dict)],
        omitted_summary=OmittedSummary(
            total_omitted=int(omitted.get("total_omitted") or 0),
            by_source_type=_string_int_dict(omitted.get("by_source_type") or {}),
        ),
    )


def _has_prompt_assets(report: RadarReport) -> bool:
    overrides = report.run_summary.config_overrides
    return all(
        overrides.get(key)
        for key in (
            "analyst_prompt_hash",
            "schema_repair_prompt_hash",
            "html_design_prompt_hash",
        )
    )


def _missing_demo_brief_fields(demo_brief: DemoBrief) -> bool:
    values = [
        demo_brief.one_screen_product_shape,
        demo_brief.core_interaction,
        demo_brief.data_needed,
        demo_brief.prototype_panel.one_screen_mock,
        demo_brief.prototype_panel.core_interaction_state,
        demo_brief.prototype_panel.empty_state,
        demo_brief.prototype_panel.success_state,
        demo_brief.prototype_panel.data_placeholders,
        demo_brief.prototype_prompt,
        demo_brief.boundary_48h,
        demo_brief.demo_success_signal,
        demo_brief.demo_kill_signal,
    ]
    return any(not value for value in values)


def _pack_item(item: dict[str, Any]) -> EvidencePackItem:
    return EvidencePackItem(
        evidence_id=str(item["evidence_id"]),
        source_type=str(item["source_type"]),
        source_ref=str(item["source_ref"]),
        title=str(item["title"]),
        summary=str(item["summary"]),
        raw_excerpt=str(item["raw_excerpt"]),
        observed_at=ensure_utc_datetime(item["observed_at"]),
        recurrence_count=int(item["recurrence_count"]),
        confidence=float(item["confidence"]),
    )


def _string_int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(item) for key, item in value.items()}
