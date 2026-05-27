"""Connector 输出的原始事件模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator

from tradar.schemas.time import ensure_utc_datetime


class RawEvent(BaseModel):
    source_type: str
    source_id: str
    source_path: str
    captured_at: datetime
    event_time: datetime | None = None
    actor: str | None = None
    title: str
    raw_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)

    @validator("captured_at", "event_time", pre=True, always=True)
    def _normalize_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        return ensure_utc_datetime(value)

    @root_validator(skip_on_failure=True)
    def _default_event_time(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("event_time") is None:
            values["event_time"] = values.get("captured_at")
        return values
