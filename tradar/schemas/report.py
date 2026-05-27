"""结构化项目雷达报告模型。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator

from tradar.schemas.run import RunSummary


def _normalize_title(title: str) -> str:
    lowered = title.strip().lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered).strip("-")


def generate_card_id(title: str, evidence_ids: list[str]) -> str:
    seed = _normalize_title(title) + "|" + ",".join(evidence_ids[:5])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return "card_" + digest


class SearchTrace(BaseModel):
    used_search: bool = False
    query_summary: str = ""
    sources_consulted: list[str] = Field(default_factory=list)
    impact: str = "none"

    @validator("impact")
    def _impact_must_be_known(cls, value: str) -> str:
        if value not in {"none", "weak", "medium", "strong"}:
            raise ValueError("impact must be none, weak, medium, or strong")
        return value


class PrototypePanel(BaseModel):
    one_screen_mock: str
    core_interaction_state: str
    empty_state: str
    success_state: str
    data_placeholders: list[str]


class DemoBrief(BaseModel):
    one_screen_product_shape: str
    core_interaction: str
    data_needed: list[str]
    prototype_panel: PrototypePanel
    prototype_prompt: str
    boundary_48h: str
    demo_success_signal: str
    demo_kill_signal: str


class CredibleSuccessPath(BaseModel):
    narrow_user: str
    current_alternative: str
    credible_demand_evidence: str
    first_distribution_path: str
    two_week_validation_signal: str
    kill_signal: str


class OpportunityCard(BaseModel):
    title: str
    card_id: str | None = None
    status_hint: str = "new"
    one_sentence: str
    evidence_ids: list[str]
    evidence_notes: list[str]
    why_you: list[str]
    why_now: list[str]
    first_users: str
    demo_48h: list[str]
    adjacent_products: list[str] = Field(default_factory=list)
    search_trace: SearchTrace = Field(default_factory=SearchTrace)
    risks: list[str]
    kill_signals: list[str]
    demo_brief: DemoBrief | None = None
    credible_success_path: CredibleSuccessPath | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("card_id", always=True)
    def _default_card_id(cls, value: str | None, values: dict[str, Any]) -> str:
        if value:
            return value
        return generate_card_id(values.get("title", "untitled"), values.get("evidence_ids", []))

    @validator("status_hint")
    def _status_hint_must_be_known(cls, value: str) -> str:
        if value not in {"new", "recurring", "previously_seen"}:
            raise ValueError("status_hint must be new, recurring, or previously_seen")
        return value

    @validator("evidence_ids")
    def _evidence_ids_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError("opportunity card must reference at least two evidence ids")
        return value


class ThisWeeksDemo(BaseModel):
    card_id: str
    title: str
    summary: str
    evidence_strength: str
    start_command: str
    skip_command: str


class DecisionPrompt(BaseModel):
    suggested_start_card_id: str | None = None
    start_command: str | None = None
    snooze_command: str | None = None
    reject_command: str | None = None
    should_not_do: list[str] = Field(default_factory=list)
    needs_user_confirmation: list[str] = Field(default_factory=list)


class RadarReport(BaseModel):
    run_summary: RunSummary
    opportunity_cards: list[OpportunityCard]
    this_weeks_demo: ThisWeeksDemo | None = None
    decision_prompt: DecisionPrompt

    @root_validator(skip_on_failure=True)
    def _demo_must_reference_existing_card(cls, values: dict[str, Any]) -> dict[str, Any]:
        demo = values.get("this_weeks_demo")
        cards = values.get("opportunity_cards") or []
        if demo is None:
            return values
        known_card_ids = {card.card_id for card in cards}
        if demo.card_id not in known_card_ids:
            raise ValueError("this_weeks_demo.card_id must match an opportunity card")
        return values
