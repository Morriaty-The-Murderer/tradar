from __future__ import annotations

from datetime import UTC, datetime

from tradar.evidence.normalizer import normalize_raw_event
from tradar.schemas import RawEvent


def test_normalizer_builds_stable_fingerprints_and_hashes() -> None:
    event = RawEvent(
        source_type="project_docs",
        source_id="docs/tradar-mvp.md",
        source_path="/repo/docs/tradar-mvp.md",
        captured_at="2026-05-24T07:00:00Z",
        event_time="2026-05-23T23:00:00Z",
        title="Tradar MVP",
        raw_text="Tradar reads local agent sessions and produces evidence-backed cards.",
        metadata={"root": "/repo"},
        parse_warnings=["missing true author time"],
    )

    evidence = normalize_raw_event(
        event,
        observed_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
    )

    assert evidence.id.startswith("ev_")
    assert evidence.source_type == "project_docs"
    assert evidence.source_ref == "docs/tradar-mvp.md"
    assert len(evidence.source_fingerprint) == 64
    assert len(evidence.content_hash) == 64
    assert evidence.observed_at == datetime(2026, 5, 23, 23, 0, tzinfo=UTC)
    assert evidence.first_seen_at == datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    assert evidence.last_seen_at == datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    assert evidence.recurrence_count == 1
    assert evidence.parse_warnings == ["missing true author time"]


def test_normalizer_truncates_raw_excerpt_without_changing_content_hash() -> None:
    long_text = "Tradar " * 200
    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/sessions/session-1.jsonl",
        captured_at="2026-05-24T07:00:00Z",
        title="Long session",
        raw_text=long_text,
    )

    evidence = normalize_raw_event(event, max_excerpt_chars=80)
    same_evidence = normalize_raw_event(event, max_excerpt_chars=120)

    assert len(evidence.raw_excerpt) <= 80
    assert evidence.raw_excerpt.endswith("...")
    assert evidence.content_hash == same_evidence.content_hash
