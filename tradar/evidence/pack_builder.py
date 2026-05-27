"""Evidence Pack 构建。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from tradar.schemas import Evidence

DEFAULT_SOURCE_ORDER = [
    "codex_session",
    "claude_code_session",
    "project_docs",
    "git_commit",
]

DEFAULT_MIN_PER_SOURCE = {
    "codex_session": 20,
    "claude_code_session": 20,
    "project_docs": 10,
    "git_commit": 10,
}


@dataclass(frozen=True)
class EvidencePackItem:
    evidence_id: str
    source_type: str
    source_ref: str
    title: str
    summary: str
    raw_excerpt: str
    observed_at: datetime
    recurrence_count: int
    confidence: float


@dataclass(frozen=True)
class OmittedSummary:
    total_omitted: int
    by_source_type: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidencePack:
    items: list[EvidencePackItem]
    omitted_summary: OmittedSummary


def build_evidence_pack(
    evidence: Iterable[Evidence],
    max_evidence_items: int = 120,
    max_pack_tokens: int = 24000,
    min_per_source: dict[str, int] | None = None,
) -> EvidencePack:
    if max_evidence_items < 1:
        raise ValueError("max_evidence_items must be positive")
    if max_pack_tokens < 1:
        raise ValueError("max_pack_tokens must be positive")

    evidence_list = list(evidence)
    selected: list[Evidence] = []
    selected_ids: set[str] = set()
    selected_tokens = 0

    by_source: dict[str, list[Evidence]] = {}
    for item in evidence_list:
        by_source.setdefault(item.source_type, []).append(item)
    requested_minimums = min_per_source or DEFAULT_MIN_PER_SOURCE
    minimums = _effective_minimums(requested_minimums, by_source, max_evidence_items)

    for source_type in DEFAULT_SOURCE_ORDER:
        if len(selected) >= max_evidence_items:
            break
        quota = minimums.get(source_type, 0)
        if quota < 1:
            continue
        bucket = sorted(by_source.get(source_type, []), key=_ranking_key)
        for candidate in bucket[:quota]:
            if len(selected) >= max_evidence_items:
                break
            candidate_tokens = _estimated_tokens(candidate)
            if selected_tokens + candidate_tokens > max_pack_tokens:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.id)
            selected_tokens += candidate_tokens

    remaining = [item for item in evidence_list if item.id not in selected_ids]
    for candidate in sorted(remaining, key=_ranking_key):
        if len(selected) >= max_evidence_items:
            break
        candidate_tokens = _estimated_tokens(candidate)
        if selected_tokens + candidate_tokens > max_pack_tokens:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.id)
        selected_tokens += candidate_tokens

    omitted = [item for item in evidence_list if item.id not in selected_ids]
    omitted_by_source: dict[str, int] = {}
    for item in omitted:
        omitted_by_source[item.source_type] = omitted_by_source.get(item.source_type, 0) + 1

    return EvidencePack(
        items=[_to_pack_item(item) for item in selected],
        omitted_summary=OmittedSummary(
            total_omitted=len(omitted),
            by_source_type=omitted_by_source,
        ),
    )


def _ranking_key(evidence: Evidence) -> tuple[int, float, str]:
    return (-evidence.recurrence_count, -evidence.observed_at.timestamp(), evidence.id)


def _effective_minimums(
    requested_minimums: dict[str, int],
    by_source: dict[str, list[Evidence]],
    max_evidence_items: int,
) -> dict[str, int]:
    present_minimums = {
        source_type: min(quota, len(by_source.get(source_type, [])))
        for source_type, quota in requested_minimums.items()
        if quota > 0 and by_source.get(source_type)
    }
    if sum(present_minimums.values()) <= max_evidence_items:
        return present_minimums

    scaled: dict[str, int] = {}
    remaining_slots = max_evidence_items
    for source_type in DEFAULT_SOURCE_ORDER:
        if remaining_slots <= 0:
            break
        if not by_source.get(source_type):
            continue
        scaled[source_type] = 1
        remaining_slots -= 1
    return scaled


def _estimated_tokens(evidence: Evidence) -> int:
    text = "\n".join([evidence.title, evidence.summary, evidence.raw_excerpt])
    return max(1, (len(text) + 3) // 4)


def _to_pack_item(evidence: Evidence) -> EvidencePackItem:
    return EvidencePackItem(
        evidence_id=evidence.id,
        source_type=evidence.source_type,
        source_ref=evidence.source_ref,
        title=evidence.title,
        summary=evidence.summary,
        raw_excerpt=evidence.raw_excerpt,
        observed_at=evidence.observed_at,
        recurrence_count=evidence.recurrence_count,
        confidence=evidence.confidence,
    )
