"""SQLite Evidence Store。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from tradar.schemas import Evidence, RunRecord
from tradar.schemas.time import ensure_utc_datetime


class EvidenceStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    recurrence_count INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    raw_excerpt TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    parse_warnings_json TEXT NOT NULL,
                    UNIQUE(source_fingerprint, content_hash)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_observed_at ON evidence(observed_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_source_type ON evidence(source_type)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_watermarks (
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    last_scan_at TEXT NOT NULL,
                    last_successful_scan_at TEXT,
                    evidence_count_delta INTEGER NOT NULL,
                    warning_count_delta INTEGER NOT NULL,
                    file_count_delta INTEGER NOT NULL DEFAULT 0,
                    elapsed_ms INTEGER NOT NULL DEFAULT 0,
                    scan_status TEXT NOT NULL,
                    PRIMARY KEY(source_type, source_ref)
                )
                """
            )
            self._ensure_column(
                conn,
                table="scan_watermarks",
                column="file_count_delta",
                definition="INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                conn,
                table="scan_watermarks",
                column="elapsed_ms",
                definition="INTEGER NOT NULL DEFAULT 0",
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_record_json TEXT NOT NULL
                )
                """
            )

    def upsert_evidence(self, evidence: Evidence) -> Evidence:
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM evidence
                WHERE source_fingerprint = ? AND content_hash = ?
                """,
                (evidence.source_fingerprint, evidence.content_hash),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO evidence (
                        id, source_type, source_path, source_ref, source_fingerprint,
                        content_hash, created_at, observed_at, first_seen_at, last_seen_at,
                        recurrence_count, title, summary, raw_excerpt, tags_json,
                        confidence, parse_warnings_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._to_row_values(evidence),
                )
            else:
                first_seen_at = self._parse_dt(existing["first_seen_at"])
                previous_last_seen_at = self._parse_dt(existing["last_seen_at"])
                next_last_seen_at = max(previous_last_seen_at, evidence.last_seen_at)
                recurrence_count = int(existing["recurrence_count"]) + 1
                conn.execute(
                    """
                    UPDATE evidence
                    SET source_path = ?,
                        source_ref = ?,
                        created_at = ?,
                        observed_at = ?,
                        first_seen_at = ?,
                        last_seen_at = ?,
                        recurrence_count = ?,
                        title = ?,
                        summary = ?,
                        raw_excerpt = ?,
                        tags_json = ?,
                        confidence = ?,
                        parse_warnings_json = ?
                    WHERE id = ?
                    """,
                    (
                        evidence.source_path,
                        evidence.source_ref,
                        self._dt(evidence.created_at),
                        self._dt(evidence.observed_at),
                        self._dt(first_seen_at),
                        self._dt(next_last_seen_at),
                        recurrence_count,
                        evidence.title,
                        evidence.summary,
                        evidence.raw_excerpt,
                        json.dumps(evidence.tags, ensure_ascii=False),
                        evidence.confidence,
                        json.dumps(evidence.parse_warnings, ensure_ascii=False),
                        existing["id"],
                    ),
                )

            row = conn.execute(
                """
                SELECT * FROM evidence
                WHERE source_fingerprint = ? AND content_hash = ?
                """,
                (evidence.source_fingerprint, evidence.content_hash),
            ).fetchone()
            if row is None:
                raise RuntimeError("evidence upsert failed")
            return self._from_row(row)

    def list_evidence_since(self, since: datetime) -> list[Evidence]:
        since_utc = ensure_utc_datetime(since)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM evidence
                WHERE observed_at >= ?
                ORDER BY observed_at ASC, id ASC
                """,
                (self._dt(since_utc),),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def record_scan_watermark(
        self,
        source_type: str,
        source_ref: str,
        scanned_at: datetime,
        evidence_count_delta: int,
        warning_count_delta: int,
        scan_status: str,
        file_count_delta: int = 0,
        elapsed_ms: int = 0,
    ) -> None:
        scanned_at_utc = ensure_utc_datetime(scanned_at)
        successful_at = scanned_at_utc if scan_status == "success" else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scan_watermarks (
                    source_type, source_ref, last_scan_at, last_successful_scan_at,
                    evidence_count_delta, warning_count_delta, file_count_delta, elapsed_ms,
                    scan_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_ref) DO UPDATE SET
                    last_scan_at = excluded.last_scan_at,
                    last_successful_scan_at = excluded.last_successful_scan_at,
                    evidence_count_delta = excluded.evidence_count_delta,
                    warning_count_delta = excluded.warning_count_delta,
                    file_count_delta = excluded.file_count_delta,
                    elapsed_ms = excluded.elapsed_ms,
                    scan_status = excluded.scan_status
                """,
                (
                    source_type,
                    source_ref,
                    self._dt(scanned_at_utc),
                    self._dt(successful_at) if successful_at else None,
                    evidence_count_delta,
                    warning_count_delta,
                    file_count_delta,
                    elapsed_ms,
                    scan_status,
                ),
            )

    def list_scan_watermarks(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source_type, source_ref, last_scan_at, last_successful_scan_at,
                       evidence_count_delta, warning_count_delta, file_count_delta,
                       elapsed_ms, scan_status
                FROM scan_watermarks
                ORDER BY source_type ASC, source_ref ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_run(self, record: RunRecord) -> RunRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, started_at, status, run_record_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    status = excluded.status,
                    run_record_json = excluded.run_record_json
                """,
                (
                    record.run_id,
                    self._dt(record.started_at),
                    record.status,
                    record.json(),
                ),
            )
        loaded = self.get_run(record.run_id)
        if loaded is None:
            raise RuntimeError("run record save failed")
        return loaded

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_record_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunRecord.parse_raw(row["run_record_json"])

    def list_runs(self) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_record_json
                FROM runs
                ORDER BY started_at ASC, run_id ASC
                """
            ).fetchall()
        return [RunRecord.parse_raw(row["run_record_json"]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        existing_columns = {
            str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _to_row_values(self, evidence: Evidence) -> Sequence[Any]:
        return (
            evidence.id,
            evidence.source_type,
            evidence.source_path,
            evidence.source_ref,
            evidence.source_fingerprint,
            evidence.content_hash,
            self._dt(evidence.created_at),
            self._dt(evidence.observed_at),
            self._dt(evidence.first_seen_at),
            self._dt(evidence.last_seen_at),
            evidence.recurrence_count,
            evidence.title,
            evidence.summary,
            evidence.raw_excerpt,
            json.dumps(evidence.tags, ensure_ascii=False),
            evidence.confidence,
            json.dumps(evidence.parse_warnings, ensure_ascii=False),
        )

    def _from_row(self, row: sqlite3.Row) -> Evidence:
        return Evidence(
            id=row["id"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            source_ref=row["source_ref"],
            source_fingerprint=row["source_fingerprint"],
            content_hash=row["content_hash"],
            created_at=self._parse_dt(row["created_at"]),
            observed_at=self._parse_dt(row["observed_at"]),
            first_seen_at=self._parse_dt(row["first_seen_at"]),
            last_seen_at=self._parse_dt(row["last_seen_at"]),
            recurrence_count=int(row["recurrence_count"]),
            title=row["title"],
            summary=row["summary"],
            raw_excerpt=row["raw_excerpt"],
            tags=self._loads_list(row["tags_json"]),
            confidence=float(row["confidence"]),
            parse_warnings=self._loads_list(row["parse_warnings_json"]),
        )

    @staticmethod
    def _loads_list(value: str) -> list[str]:
        loaded = json.loads(value)
        if not isinstance(loaded, list):
            return []
        return [str(item) for item in loaded]

    @staticmethod
    def _dt(value: datetime) -> str:
        return ensure_utc_datetime(value).isoformat()

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        return ensure_utc_datetime(value)
