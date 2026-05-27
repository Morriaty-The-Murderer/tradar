"""轻量项目卡决策状态。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, validator

from tradar.schemas.time import ensure_utc_datetime, utc_now


class DecisionState(BaseModel):
    card_id: str
    decision: str
    decided_at: datetime = Field(default_factory=utc_now)
    note: str | None = None

    @validator("decision")
    def _decision_must_be_known(cls, value: str) -> str:
        if value not in {"accept", "snooze", "reject"}:
            raise ValueError("decision must be accept, snooze, or reject")
        return value

    @validator("decided_at", pre=True)
    def _normalize_decided_at(cls, value: object) -> datetime:
        return ensure_utc_datetime(value)
