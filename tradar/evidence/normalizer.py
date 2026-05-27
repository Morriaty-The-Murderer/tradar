"""RawEvent 到 Evidence 的最小归一化逻辑。"""

from __future__ import annotations

import hashlib
from datetime import datetime

from tradar.schemas import Evidence, RawEvent
from tradar.schemas.time import ensure_utc_datetime, utc_now


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return "." * max_chars
    return value[: max_chars - 3].rstrip() + "..."


def normalize_raw_event(
    event: RawEvent,
    observed_at: datetime | None = None,
    max_excerpt_chars: int = 500,
) -> Evidence:
    seen_at = ensure_utc_datetime(observed_at) if observed_at is not None else utc_now()
    event_time = event.event_time or event.captured_at
    source_ref = event.source_id
    source_fingerprint = _sha256(
        "\n".join([event.source_type, event.source_id, event.source_path])
    )
    content_hash = _sha256(event.raw_text)
    evidence_id = "ev_" + _sha256(source_fingerprint + content_hash)[:16]

    return Evidence(
        id=evidence_id,
        source_type=event.source_type,
        source_path=event.source_path,
        source_ref=source_ref,
        source_fingerprint=source_fingerprint,
        content_hash=content_hash,
        created_at=seen_at,
        observed_at=event_time,
        first_seen_at=seen_at,
        last_seen_at=seen_at,
        recurrence_count=1,
        title=event.title,
        summary=event.title,
        raw_excerpt=_truncate(event.raw_text.strip(), max_excerpt_chars),
        tags=[event.source_type],
        confidence=1.0,
        parse_warnings=list(event.parse_warnings),
    )
