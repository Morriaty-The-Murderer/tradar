"""Run 级状态模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from tradar.schemas.time import ensure_utc_datetime, utc_now


def _new_run_id() -> str:
    return "run_" + uuid4().hex


class RunSummary(BaseModel):
    run_id: str
    generated_at: datetime
    timezone: str
    days_window: int
    evidence_count: int
    warning_count: int
    rendered_by: str
    config_path: str | None = None
    config_overrides: dict[str, str] = Field(default_factory=dict)
    sources_requested: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    debug_bundle_path: str | None = None
    confidence_note: str | None = None
    report_status: str = "complete"
    next_steps: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)
    warning_events: dict[str, int] = Field(default_factory=dict)
    source_warning_counts: dict[str, int] = Field(default_factory=dict)
    source_scan_file_counts: dict[str, int] = Field(default_factory=dict)
    source_scan_elapsed_ms: dict[str, int] = Field(default_factory=dict)
    search_used_count: int = 0
    search_trace_summary: str = ""
    agent_elapsed_ms: int | None = None
    repair_used: bool = False
    repair_elapsed_ms: int | None = None
    enhanced_elapsed_ms: int | None = None

    @validator("generated_at", pre=True)
    def _normalize_generated_at(cls, value: object) -> datetime:
        return ensure_utc_datetime(value)

    @validator("days_window")
    def _days_window_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("days_window must be positive")
        return value

    @validator("rendered_by")
    def _rendered_by_must_be_known(cls, value: str) -> str:
        if value not in {"base", "enhanced"}:
            raise ValueError("rendered_by must be base or enhanced")
        return value

    @validator("report_status")
    def _report_status_must_be_known(cls, value: str) -> str:
        if value not in {"complete", "partial", "empty", "low_confidence"}:
            raise ValueError("report_status must be complete, partial, empty, or low_confidence")
        return value


class RunRecord(BaseModel):
    run_id: str = Field(default_factory=_new_run_id)
    started_at: datetime = Field(default_factory=utc_now)
    status: str = "created"
    run_summary: RunSummary | None = None
    warnings: list[str] = Field(default_factory=list)

    @validator("started_at", pre=True)
    def _normalize_started_at(cls, value: object) -> datetime:
        return ensure_utc_datetime(value)
