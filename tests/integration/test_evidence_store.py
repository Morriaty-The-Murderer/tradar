from __future__ import annotations

from datetime import UTC, datetime

from tradar.evidence.normalizer import normalize_raw_event
from tradar.evidence.store import EvidenceStore
from tradar.schemas import RawEvent, RunRecord, RunSummary


def test_evidence_store_upserts_duplicate_evidence_and_preserves_first_seen(tmp_path) -> None:
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/sessions/session-1.jsonl",
        captured_at="2026-05-24T07:00:00Z",
        title="Tradar",
        raw_text="Build a local project radar from agent sessions.",
    )
    first = normalize_raw_event(
        event,
        observed_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
    )
    second = first.copy(
        update={"last_seen_at": datetime(2026, 5, 24, 9, 0, tzinfo=UTC)}
    )

    saved_first = store.upsert_evidence(first)
    saved_second = store.upsert_evidence(second)
    rows = store.list_evidence_since(datetime(2026, 5, 24, 0, 0, tzinfo=UTC))

    assert saved_first.id == saved_second.id
    assert saved_second.recurrence_count == 2
    assert saved_second.first_seen_at == datetime(2026, 5, 24, 8, 0, tzinfo=UTC)
    assert saved_second.last_seen_at == datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
    assert len(rows) == 1
    assert rows[0].id == first.id


def test_evidence_store_filters_by_observed_time(tmp_path) -> None:
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    old_event = RawEvent(
        source_type="project_docs",
        source_id="old.md",
        source_path="/repo/old.md",
        captured_at="2026-04-01T00:00:00Z",
        title="Old",
        raw_text="Old evidence.",
    )
    recent_event = RawEvent(
        source_type="project_docs",
        source_id="recent.md",
        source_path="/repo/recent.md",
        captured_at="2026-05-24T00:00:00Z",
        title="Recent",
        raw_text="Recent evidence.",
    )

    store.upsert_evidence(normalize_raw_event(old_event))
    store.upsert_evidence(normalize_raw_event(recent_event))

    rows = store.list_evidence_since(datetime(2026, 5, 1, 0, 0, tzinfo=UTC))

    assert [row.title for row in rows] == ["Recent"]


def test_evidence_store_records_scan_file_count_and_elapsed_time(tmp_path) -> None:
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    store.record_scan_watermark(
        source_type="project_docs",
        source_ref="/repo",
        scanned_at=datetime(2026, 5, 24, 8, 0, tzinfo=UTC),
        evidence_count_delta=2,
        warning_count_delta=1,
        scan_status="success",
        file_count_delta=3,
        elapsed_ms=42,
    )

    rows = store.list_scan_watermarks()

    assert rows[0]["file_count_delta"] == 3
    assert rows[0]["elapsed_ms"] == 42


def test_evidence_store_records_and_lists_run_records(tmp_path) -> None:
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    summary = RunSummary(
        run_id="run_20260525010101",
        generated_at="2026-05-25T01:01:01Z",
        timezone="Asia/Shanghai",
        days_window=30,
        evidence_count=5,
        warning_count=1,
        rendered_by="base",
        report_status="complete",
    )
    record = RunRecord(
        run_id=summary.run_id,
        status="generated",
        run_summary=summary,
        warnings=["connector.parse_warning"],
    )

    store.record_run(record)
    loaded = store.get_run(record.run_id)
    all_runs = store.list_runs()

    assert loaded == record
    assert all_runs == [record]
