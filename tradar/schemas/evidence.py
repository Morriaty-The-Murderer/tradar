"""标准化后的 evidence 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, validator

from tradar.schemas.time import ensure_utc_datetime


class Evidence(BaseModel):
    id: str
    source_type: str
    source_path: str
    source_ref: str
    source_fingerprint: str
    content_hash: str
    created_at: datetime
    observed_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    recurrence_count: int = 1
    title: str
    summary: str
    raw_excerpt: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    parse_warnings: list[str] = Field(default_factory=list)

    @validator("created_at", "observed_at", "first_seen_at", "last_seen_at", pre=True)
    def _normalize_datetime(cls, value: object) -> datetime:
        return ensure_utc_datetime(value)

    @validator("recurrence_count")
    def _recurrence_count_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("recurrence_count must be at least 1")
        return value

    @validator("confidence")
    def _confidence_must_be_probability(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value
