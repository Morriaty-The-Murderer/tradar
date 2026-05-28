from __future__ import annotations

import json
from pathlib import Path

import pytest

import tradar.cli.app as cli_module
from tradar.agent_runner.base import AgentRawOutput, MockAgentAdapter
from tradar.agent_runner.schema_repair import (
    AgentOutputSchemaError,
    FixedSchemaRepairAdapter,
)
from tradar.cli.app import generate_report, scan_sources
from tradar.config.loader import load_config
from tradar.evidence.store import EvidenceStore
from tradar.schemas import DecisionState, generate_card_id
from tradar.schemas.time import ensure_utc_datetime
from tradar.state.decisions import DecisionStateStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def test_generate_with_agent_adapter_writes_validated_report(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(evidence_ids=evidence_ids),
            elapsed_ms=12,
            search_trace_summary="no external search",
        )
    )

    report_path = generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)

    run_dir = report_path.parent
    validated_report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    raw_output = json.loads((run_dir / "agent_raw_output.json").read_text(encoding="utf-8"))
    html = report_path.read_text(encoding="utf-8")

    assert validated_report["opportunity_cards"][0]["title"] == "Tradar Agent Path"
    assert validated_report["opportunity_cards"][0]["evidence_ids"] == evidence_ids
    assert validated_report["run_summary"]["run_id"] == run_dir.name
    assert raw_output["mode"] == "codex"
    assert len(raw_output["prompt_assets"]["analyst"]["content_hash"]) == 64
    assert "Tradar Agent Path" in html


def test_generate_records_agent_search_trace_in_run_summary(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(evidence_ids=evidence_ids, used_search=True),
            elapsed_ms=37,
            search_trace_summary="searched official docs for market context",
        )
    )

    report_path = generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)

    validated_report = json.loads(
        (report_path.parent / "validated_report.json").read_text(encoding="utf-8")
    )
    summary = validated_report["run_summary"]

    assert summary["search_used_count"] == 1
    assert summary["search_trace_summary"] == "searched official docs for market context"
    assert summary["agent_elapsed_ms"] == 37


def test_generate_with_agent_adapter_rejects_unknown_evidence_id(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    known_evidence_id = _first_evidence_ids(config.database_path, 1)[0]
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(evidence_ids=[known_evidence_id, "ev_missing"]),
            elapsed_ms=12,
        )
    )

    with pytest.raises(AgentOutputSchemaError, match="unknown evidence ids"):
        generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)


def test_generate_with_agent_adapter_uses_one_schema_repair(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text='{"opportunity_cards": []}',
            elapsed_ms=12,
        )
    )
    repair_adapter = FixedSchemaRepairAdapter(_agent_report_json(evidence_ids=evidence_ids))

    report_path = generate_report(
        config,
        days=30,
        agent_mode="codex",
        agent_adapter=adapter,
        repair_adapter=repair_adapter,
    )

    assert repair_adapter.calls == 1
    assert report_path.exists()
    validated_report = json.loads(
        (report_path.parent / "validated_report.json").read_text(encoding="utf-8")
    )
    summary = validated_report["run_summary"]
    assert summary["repair_used"] is True
    assert summary["repair_elapsed_ms"] >= 0


def test_generate_overrides_agent_card_id_status_and_decision_commands(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(
                evidence_ids=evidence_ids,
                card_id="agent_supplied_card",
                status_hint="previously_seen",
                include_demo=True,
            ),
            elapsed_ms=12,
        )
    )
    expected_card_id = generate_card_id("Tradar Agent Path", evidence_ids)

    report_path = generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)

    validated_report = json.loads(
        (report_path.parent / "validated_report.json").read_text(encoding="utf-8")
    )
    card = validated_report["opportunity_cards"][0]
    decision_prompt = validated_report["decision_prompt"]

    assert card["card_id"] == expected_card_id
    assert card["status_hint"] != "previously_seen"
    assert validated_report["this_weeks_demo"]["card_id"] == expected_card_id
    assert decision_prompt["suggested_start_card_id"] == expected_card_id
    assert decision_prompt["start_command"] == f"tradar accept {expected_card_id}"
    assert decision_prompt["snooze_command"] == f"tradar snooze {expected_card_id}"
    assert decision_prompt["reject_command"] == f"tradar reject {expected_card_id}"


def test_generate_marks_card_previously_seen_from_decision_state(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    expected_card_id = generate_card_id("Tradar Agent Path", evidence_ids)
    decision_store = DecisionStateStore(config.database_path)
    decision_store.initialize()
    decision_store.save(DecisionState(card_id=expected_card_id, decision="snooze"))
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(evidence_ids=evidence_ids),
            elapsed_ms=12,
        )
    )

    report_path = generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)

    validated_report = json.loads(
        (report_path.parent / "validated_report.json").read_text(encoding="utf-8")
    )
    assert validated_report["opportunity_cards"][0]["status_hint"] == "previously_seen"


def test_generate_respects_disabled_agent_raw_output_config(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, save_agent_raw_output=False)
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    adapter = MockAgentAdapter(
        AgentRawOutput(
            raw_text=_agent_report_json(evidence_ids=evidence_ids),
            elapsed_ms=12,
        )
    )

    report_path = generate_report(config, days=30, agent_mode="codex", agent_adapter=adapter)

    run_dir = report_path.parent
    assert not (run_dir / "agent_raw_output.json").exists()
    assert (run_dir / "validated_report.json").exists()
    assert (run_dir / "warnings.jsonl").exists()


def test_generate_uses_configured_codex_adapter_timeouts(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(
        tmp_path,
        agent_timeout_seconds=11,
        schema_repair_timeout_seconds=12,
        codex_binary="/opt/bin/codex-preview",
    )
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    captured: dict[str, int] = {}

    class RecordingCodexAdapter:
        def __init__(self, codex_binary: str = "codex", timeout_seconds: int = 300) -> None:
            captured["codex_binary"] = codex_binary
            captured["agent_timeout_seconds"] = timeout_seconds

        def run(self, **kwargs):
            return AgentRawOutput(
                raw_text=_agent_report_json(evidence_ids=evidence_ids),
                elapsed_ms=1,
            )

    class RecordingSchemaRepairAdapter:
        def __init__(
            self,
            codex_binary: str = "codex",
            timeout_seconds: int = 300,
            **kwargs,
        ) -> None:
            captured["schema_repair_codex_binary"] = codex_binary
            captured["schema_repair_timeout_seconds"] = timeout_seconds

        def repair(self, raw_text: str, error_message: str) -> str:
            raise AssertionError("schema repair should not be called for valid output")

    monkeypatch.setattr(cli_module, "CodexAdapter", RecordingCodexAdapter)
    monkeypatch.setattr(cli_module, "CodexSchemaRepairAdapter", RecordingSchemaRepairAdapter)

    generate_report(config, days=30, agent_mode="codex")

    assert captured["codex_binary"] == "/opt/bin/codex-preview"
    assert captured["agent_timeout_seconds"] == 11
    assert captured["schema_repair_codex_binary"] == "/opt/bin/codex-preview"
    assert captured["schema_repair_timeout_seconds"] == 12


def test_generate_uses_configured_claude_code_adapter(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(
        tmp_path,
        agent_timeout_seconds=21,
        schema_repair_timeout_seconds=22,
        claude_binary="/opt/bin/claude-code",
    )
    config = load_config(config_path)
    scan_sources(config)
    evidence_ids = _first_evidence_ids(config.database_path, 2)
    captured: dict[str, object] = {}

    class RecordingClaudeCodeAdapter:
        def __init__(self, claude_binary: str = "claude", timeout_seconds: int = 300) -> None:
            captured["claude_binary"] = claude_binary
            captured["agent_timeout_seconds"] = timeout_seconds

        def run(self, **kwargs):
            return AgentRawOutput(
                raw_text=_agent_report_json(evidence_ids=evidence_ids),
                elapsed_ms=1,
            )

    class RecordingClaudeCodeSchemaRepairAdapter:
        def __init__(
            self,
            claude_binary: str = "claude",
            timeout_seconds: int = 300,
            **kwargs,
        ) -> None:
            captured["schema_repair_claude_binary"] = claude_binary
            captured["schema_repair_timeout_seconds"] = timeout_seconds

        def repair(self, raw_text: str, error_message: str) -> str:
            raise AssertionError("schema repair should not be called for valid output")

    monkeypatch.setattr(cli_module, "ClaudeCodeAdapter", RecordingClaudeCodeAdapter)
    monkeypatch.setattr(
        cli_module,
        "ClaudeCodeSchemaRepairAdapter",
        RecordingClaudeCodeSchemaRepairAdapter,
    )

    generate_report(config, days=30, agent_mode="claude")

    assert captured["claude_binary"] == "/opt/bin/claude-code"
    assert captured["agent_timeout_seconds"] == 21
    assert captured["schema_repair_claude_binary"] == "/opt/bin/claude-code"
    assert captured["schema_repair_timeout_seconds"] == 22


def _write_config(
    tmp_path: Path,
    save_agent_raw_output: bool = True,
    agent_timeout_seconds: int | None = None,
    schema_repair_timeout_seconds: int | None = None,
    codex_binary: str | None = None,
    claude_binary: str | None = None,
) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                'codex_session_paths = ["{}"]'.format(FIXTURES / "codex"),
                'claude_project_paths = ["{}"]'.format(FIXTURES / "claude"),
                'project_roots = ["{}"]'.format(FIXTURES / "project_docs"),
                'output_dir = "{}"'.format(tmp_path / "runs"),
                'state_dir = "{}"'.format(tmp_path / "state"),
                "days_window = 30",
                "allow_broad_root = false",
                f"save_agent_raw_output = {str(save_agent_raw_output).lower()}",
                *(
                    [f"agent_timeout_seconds = {agent_timeout_seconds}"]
                    if agent_timeout_seconds is not None
                    else []
                ),
                *(
                    [f"schema_repair_timeout_seconds = {schema_repair_timeout_seconds}"]
                    if schema_repair_timeout_seconds is not None
                    else []
                ),
                *([f'codex_binary = "{codex_binary}"'] if codex_binary is not None else []),
                *([f'claude_binary = "{claude_binary}"'] if claude_binary is not None else []),
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _first_evidence_ids(database_path: Path, count: int) -> list[str]:
    store = EvidenceStore(database_path)
    evidence = store.list_evidence_since(ensure_utc_datetime("1970-01-01T00:00:00Z"))
    assert len(evidence) >= count
    return [item.id for item in evidence[:count]]


def _agent_report_json(
    evidence_ids: list[str],
    card_id: str | None = None,
    status_hint: str | None = None,
    include_demo: bool = False,
    used_search: bool = False,
) -> str:
    card = {
        "title": "Tradar Agent Path",
        "one_sentence": "Turn scanned local agent evidence into traceable project cards.",
        "evidence_ids": evidence_ids,
        "evidence_notes": [
            "The scanned evidence already points at this workflow.",
            "A second evidence item keeps the card above the golden checklist threshold.",
        ],
        "why_you": ["The user has repeated local agent workflow traces."],
        "why_now": ["The evidence store and renderer are already in place."],
        "first_users": "Solo builders who work through local coding agents.",
        "demo_48h": ["Scan local sessions.", "Run analyst agent.", "Render one report."],
        "adjacent_products": ["local-first research dashboard"],
        "search_trace": {
            "used_search": used_search,
            "query_summary": "market context" if used_search else "",
            "sources_consulted": ["official docs"] if used_search else [],
            "impact": "medium" if used_search else "none",
        },
        "risks": ["Agent output may drift without schema validation."],
        "kill_signals": ["No card is accepted after a real weekly report."],
    }
    if card_id is not None:
        card["card_id"] = card_id
    if status_hint is not None:
        card["status_hint"] = status_hint
    payload = {
        "run_summary": {
            "run_id": "agent_supplied_run",
            "generated_at": "2026-05-24T08:00:00Z",
            "timezone": "Asia/Shanghai",
            "days_window": 30,
            "evidence_count": len(evidence_ids),
            "warning_count": 0,
            "rendered_by": "base",
        },
        "opportunity_cards": [card],
        "decision_prompt": {
            "suggested_start_card_id": card_id,
            "needs_user_confirmation": ["Confirm whether to run the 48 hour demo."],
        },
    }
    if include_demo and card_id is not None:
        payload["this_weeks_demo"] = {
            "card_id": card_id,
            "title": "Tradar Agent Path",
            "summary": "Run the demo.",
            "evidence_strength": "medium",
            "start_command": f"tradar accept {card_id}",
            "skip_command": f"tradar snooze {card_id}",
        }
    return json.dumps(
        payload
    )
