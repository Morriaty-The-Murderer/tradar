from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from tradar.evidence.normalizer import normalize_raw_event
from tradar.evidence.pack_builder import build_evidence_pack
from tradar.schemas import RawEvent


def _evidence(source_type: str, source_id: str, title: str, observed_at: str, recurrence: int):
    event = RawEvent(
        source_type=source_type,
        source_id=source_id,
        source_path="/tmp/" + source_id,
        captured_at=observed_at,
        title=title,
        raw_text=title + " " + ("evidence " * 20),
    )
    evidence = normalize_raw_event(
        event,
        observed_at=datetime(2026, 5, 24, 0, 0, tzinfo=UTC),
    )
    return evidence.copy(update={"recurrence_count": recurrence, "summary": title})


def test_pack_builder_preserves_core_source_quotas_before_global_fill() -> None:
    evidence = [
        _evidence("codex_session", "codex-old", "Old codex", "2026-05-20T00:00:00Z", 1),
        _evidence("codex_session", "codex-hot", "Hot codex", "2026-05-21T00:00:00Z", 3),
        _evidence("claude_code_session", "claude-1", "Claude QA", "2026-05-22T00:00:00Z", 1),
        _evidence("project_docs", "doc-1", "Docs plan", "2026-05-23T00:00:00Z", 1),
        _evidence("git_commit", "abc1234", "Commit reason", "2026-05-24T00:00:00Z", 1),
        _evidence("project_docs", "doc-2", "Extra docs", "2026-05-24T01:00:00Z", 5),
    ]

    pack = build_evidence_pack(evidence, max_evidence_items=4)

    assert len(pack.items) == 4
    assert {item.source_type for item in pack.items} == {
        "codex_session",
        "claude_code_session",
        "project_docs",
        "git_commit",
    }
    assert pack.items[0].title == "Hot codex"
    assert pack.omitted_summary.total_omitted == 2
    assert pack.omitted_summary.by_source_type == {"codex_session": 1, "project_docs": 1}


def test_pack_builder_uses_default_source_minimums_when_budget_allows() -> None:
    evidence = []
    for source_type, count in [
        ("codex_session", 25),
        ("claude_code_session", 25),
        ("project_docs", 15),
        ("git_commit", 15),
    ]:
        for index in range(count):
            evidence.append(
                _evidence(
                    source_type,
                    f"{source_type}-{index}",
                    f"{source_type} {index}",
                    "2026-05-20T00:00:00Z",
                    1,
                )
            )

    pack = build_evidence_pack(evidence, max_evidence_items=60, max_pack_tokens=24000)
    counts = Counter(item.source_type for item in pack.items)

    assert len(pack.items) == 60
    assert counts["codex_session"] >= 20
    assert counts["claude_code_session"] >= 20
    assert counts["project_docs"] >= 10
    assert counts["git_commit"] >= 10


def test_pack_builder_uses_global_ranking_after_minimum_quotas() -> None:
    evidence = [
        _evidence("codex_session", "codex-1", "Codex", "2026-05-20T00:00:00Z", 1),
        _evidence("claude_code_session", "claude-1", "Claude", "2026-05-20T00:00:00Z", 1),
        _evidence("project_docs", "doc-1", "Docs", "2026-05-20T00:00:00Z", 1),
        _evidence("git_commit", "git-1", "Git", "2026-05-20T00:00:00Z", 1),
        _evidence("manual_note", "note-1", "Most repeated", "2026-05-21T00:00:00Z", 9),
    ]

    pack = build_evidence_pack(evidence, max_evidence_items=5)

    assert [item.title for item in pack.items][-1] == "Most repeated"
    assert pack.omitted_summary.total_omitted == 0


def test_pack_builder_respects_token_budget() -> None:
    evidence = [
        _evidence("codex_session", "codex-1", "Codex one", "2026-05-20T00:00:00Z", 1),
        _evidence("claude_code_session", "claude-1", "Claude one", "2026-05-21T00:00:00Z", 1),
        _evidence("project_docs", "doc-1", "Docs one", "2026-05-22T00:00:00Z", 1),
    ]

    pack = build_evidence_pack(evidence, max_evidence_items=10, max_pack_tokens=80)

    assert 0 < len(pack.items) < len(evidence)
    assert pack.omitted_summary.total_omitted == len(evidence) - len(pack.items)
