from __future__ import annotations

from tradar.evidence.privacy import PrivacyGate, RedactionRule
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


def test_privacy_gate_redacts_default_secret_shapes() -> None:
    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/sessions/session-1.jsonl",
        captured_at="2026-05-24T07:00:00Z",
        title="Use OPENAI_API_KEY=sk-test1234567890",
        raw_text="Set OPENAI_API_KEY=sk-test1234567890 before running the adapter.",
    )

    filtered = PrivacyGate().filter(event)

    assert "sk-test" not in filtered.title
    assert "sk-test" not in filtered.raw_text
    assert "<REDACTED>" in filtered.title
    assert "<REDACTED>" in filtered.raw_text
    assert "privacy.redacted:secret_assignment" in filtered.parse_warnings


def test_privacy_gate_configured_replacement_applies_to_default_rules() -> None:
    event = RawEvent(
        source_type="codex_session",
        source_id="session-1",
        source_path="/sessions/session-1.jsonl",
        captured_at="2026-05-24T07:00:00Z",
        title="Secret config",
        raw_text="TOKEN=TOKEN-ABCDEF123456 should not leave the machine.",
    )

    filtered = PrivacyGate.from_patterns([], replacement="REDACTED").filter(event)

    assert "<REDACTED>" not in filtered.raw_text
    assert "TOKEN-ABCDEF123456" not in filtered.raw_text
    assert "REDACTED" in filtered.raw_text


def test_privacy_gate_accepts_custom_redaction_policy_hooks() -> None:
    event = RawEvent(
        source_type="project_docs",
        source_id="notes/launch.md",
        source_path="/repo/notes/launch.md",
        captured_at="2026-05-24T07:00:00Z",
        title="Discuss VIP-1234 launch",
        raw_text="VIP-1234 should stay private but the rest of the note can be scanned.",
    )
    gate = PrivacyGate(
        redaction_rules=[
            RedactionRule(
                name="internal_ticket",
                pattern=r"VIP-\d+",
                replacement="<TICKET>",
            )
        ]
    )

    filtered = gate.filter(event)

    assert filtered.title == "Discuss <TICKET> launch"
    assert filtered.raw_text.startswith("<TICKET> should stay private")
    assert "privacy.redacted:internal_ticket" in filtered.parse_warnings
