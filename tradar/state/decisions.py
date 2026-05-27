"""轻量 decision state SQLite 存储。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tradar.schemas import DecisionState
from tradar.schemas.time import ensure_utc_datetime


class DecisionStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_state (
                    card_id TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    note TEXT
                )
                """
            )

    def save(self, state: DecisionState) -> DecisionState:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decision_state (card_id, decision, decided_at, note)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    decision = excluded.decision,
                    decided_at = excluded.decided_at,
                    note = excluded.note
                """,
                (
                    state.card_id,
                    state.decision,
                    ensure_utc_datetime(state.decided_at).isoformat(),
                    state.note,
                ),
            )
        loaded = self.get(state.card_id)
        if loaded is None:
            raise RuntimeError("decision state save failed")
        return loaded

    def get(self, card_id: str) -> DecisionState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT card_id, decision, decided_at, note FROM decision_state WHERE card_id = ?",
                (card_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def list_all(self) -> list[DecisionState]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT card_id, decision, decided_at, note
                FROM decision_state
                ORDER BY card_id ASC
                """
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DecisionState:
        return DecisionState(
            card_id=row["card_id"],
            decision=row["decision"],
            decided_at=ensure_utc_datetime(row["decided_at"]),
            note=row["note"],
        )
