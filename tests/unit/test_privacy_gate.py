from __future__ import annotations

from tradar.evidence.privacy import PrivacyGate
from tradar.schemas import RawEvent


def test_privacy_gate_v0_1_passes_event_through() -> None:
    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/sessions/session-1.jsonl",
        captured_at="2026-05-24T07:00:00Z",
        title="Build Tradar",
        raw_text="Local agent evidence should remain local.",
        parse_warnings=["fixture warning"],
    )

    filtered = PrivacyGate().filter(event)

    assert filtered is event
    assert filtered.raw_text == "Local agent evidence should remain local."
    assert filtered.parse_warnings == ["fixture warning"]
