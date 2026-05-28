from __future__ import annotations

import json
import os
import subprocess

import pytest

from tradar.agent_runner.base import (
    AgentAdapterExecutionError,
    AgentRawOutput,
    MockAgentAdapter,
    PromptAssets,
    RunContext,
    ToolPolicy,
    load_prompt_asset,
)
from tradar.agent_runner.claude_code_adapter import (
    ClaudeCodeAdapter,
    ClaudeCodeSchemaRepairAdapter,
)
from tradar.agent_runner.codex_adapter import (
    CodexAdapter,
    CodexSchemaRepairAdapter,
    _build_prompt_input,
)
from tradar.agent_runner.schema_repair import validate_or_repair_report
from tradar.evidence.pack_builder import EvidencePack, EvidencePackItem, OmittedSummary
from tradar.schemas.time import ensure_utc_datetime


def test_prompt_assets_have_content_hashes_and_mock_output_validates() -> None:
    assets = PromptAssets(
        analyst=load_prompt_asset("analyst", "tradar/agent_runner/prompts/analyst.md"),
        schema_repair=load_prompt_asset(
            "schema_repair",
            "tradar/agent_runner/prompts/schema_repair.md",
        ),
        html_design=load_prompt_asset(
            "html_design",
            "tradar/agent_runner/prompts/html_design.md",
        ),
    )
    output = _agent_output_json()
    adapter = MockAgentAdapter(AgentRawOutput(raw_text=output, elapsed_ms=10))

    raw = adapter.run(
        evidence_pack=_evidence_pack(),
        prompt_assets=assets,
        tool_policy=ToolPolicy(allow_search=False),
        run_context=RunContext(run_id="run_prompt_smoke", output_dir="/tmp/tradar"),
    )
    report = validate_or_repair_report(raw.raw_text)

    assert len(assets.analyst.content_hash) == 64
    assert len(assets.schema_repair.content_hash) == 64
    assert report.run_summary.run_id == "run_prompt_smoke"
    assert report.opportunity_cards[0].evidence_ids == ["ev_1", "ev_2"]


def test_codex_adapter_builds_command_without_running_agent() -> None:
    adapter = CodexAdapter(codex_binary="codex")

    command = adapter.build_command(prompt_path="/tmp/analyst.md", output_path="/tmp/output.json")

    assert command[:2] == ["codex", "exec"]
    assert "--output-last-message" in command
    assert "/tmp/output.json" in command
    assert command[-1] == "-"


def test_claude_code_adapter_builds_headless_json_command_without_running_agent() -> None:
    adapter = ClaudeCodeAdapter(claude_binary="claude")

    command = adapter.build_command()

    assert command == [
        "claude",
        "--bare",
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def test_claude_code_adapter_extracts_result_field_from_json_stdout(tmp_path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        assert args[0] == [
            "claude",
            "--bare",
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
        ]
        assert kwargs["input"]

        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "duration_ms": 12,
                    "result": _agent_output_json(),
                    "session_id": "claude-session",
                }
            )
            stderr = ""

        return Result()

    monkeypatch.setattr("tradar.agent_runner.claude_code_adapter.subprocess.run", fake_run)
    adapter = ClaudeCodeAdapter(claude_binary="claude", timeout_seconds=7)

    raw = adapter.run(
        evidence_pack=_evidence_pack(),
        prompt_assets=_prompt_assets(),
        tool_policy=ToolPolicy(allow_search=True),
        run_context=RunContext(run_id="run_claude_agent", output_dir=str(tmp_path / "run")),
    )

    assert raw.raw_text == _agent_output_json()
    assert raw.elapsed_ms >= 0
    assert "claude_session_id=claude-session" in raw.search_trace_summary
    assert (tmp_path / "run" / "agent_prompt.md").exists()


def test_claude_schema_repair_adapter_builds_command_without_running_agent() -> None:
    prompt = _prompt_assets().schema_repair
    adapter = ClaudeCodeSchemaRepairAdapter(prompt_asset=prompt, output_dir="/tmp/tradar")

    command = adapter.build_command()

    assert command[:4] == ["claude", "--bare", "-p", "--output-format"]
    assert "json" in command
    assert "--no-session-persistence" in command


def test_codex_prompt_omits_raw_excerpt_from_agent_payload() -> None:
    assets = PromptAssets(
        analyst=load_prompt_asset("analyst", "tradar/agent_runner/prompts/analyst.md"),
        schema_repair=load_prompt_asset(
            "schema_repair",
            "tradar/agent_runner/prompts/schema_repair.md",
        ),
        html_design=load_prompt_asset(
            "html_design",
            "tradar/agent_runner/prompts/html_design.md",
        ),
    )

    prompt = _build_prompt_input(
        evidence_pack=_evidence_pack(),
        prompt_assets=assets,
        tool_policy=ToolPolicy(allow_search=True),
        run_context=RunContext(run_id="run_prompt_smoke", output_dir="/tmp/tradar"),
    )

    assert '"summary": "Repeated work on local agent session analysis."' in prompt
    assert "raw_excerpt" not in prompt
    assert "Build Tradar from local agent sessions." not in prompt


def test_analyst_prompt_requires_two_evidence_ids_per_card() -> None:
    prompt = load_prompt_asset("analyst", "tradar/agent_runner/prompts/analyst.md")

    assert "at least 2 evidence_ids" in prompt.content


def test_prompts_name_required_nested_report_fields() -> None:
    assets = _prompt_assets()

    for field_name in [
        "title",
        "data_needed",
        "prototype_panel",
        "one_screen_mock",
        "demo_success_signal",
        "demo_kill_signal",
        "credible_demand_evidence",
        "credible_success_path.kill_signal",
        "rendered_by",
        "timezone-aware",
        "days_window",
        "boundary_48h",
    ]:
        assert field_name in assets.analyst.content
        assert field_name in assets.schema_repair.content


def test_codex_adapter_raises_execution_error_on_nonzero_exit(tmp_path) -> None:
    codex_script = tmp_path / "codex_fail.py"
    codex_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "print('codex failed before producing JSON', file=sys.stderr)",
                "sys.exit(42)",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(codex_script, 0o755)
    adapter = CodexAdapter(codex_binary=str(codex_script))

    with pytest.raises(AgentAdapterExecutionError) as exc_info:
        adapter.run(
            evidence_pack=_evidence_pack(),
            prompt_assets=_prompt_assets(),
            tool_policy=ToolPolicy(allow_search=True),
            run_context=RunContext(run_id="run_failed_agent", output_dir=str(tmp_path / "run")),
        )

    assert exc_info.value.event == "agent.execution_failed"
    assert "codex failed before producing JSON" in str(exc_info.value)
    assert (tmp_path / "run" / "agent_prompt.md").exists()


def test_codex_adapter_maps_timeout_to_registered_event(tmp_path, monkeypatch) -> None:
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("tradar.agent_runner.codex_adapter.subprocess.run", raise_timeout)
    adapter = CodexAdapter(codex_binary="codex", timeout_seconds=7)

    with pytest.raises(AgentAdapterExecutionError) as exc_info:
        adapter.run(
            evidence_pack=_evidence_pack(),
            prompt_assets=_prompt_assets(),
            tool_policy=ToolPolicy(allow_search=True),
            run_context=RunContext(run_id="run_timeout_agent", output_dir=str(tmp_path / "run")),
        )

    assert exc_info.value.event == "agent.timeout"
    assert "7" in str(exc_info.value)
    assert (tmp_path / "run" / "agent_prompt.md").exists()


def test_codex_schema_repair_adapter_builds_command_without_running_agent() -> None:
    prompt = _prompt_assets().schema_repair
    adapter = CodexSchemaRepairAdapter(prompt_asset=prompt, output_dir="/tmp/tradar")

    command = adapter.build_command(output_path="/tmp/repaired.json")

    assert command[:2] == ["codex", "exec"]
    assert "--output-last-message" in command
    assert "/tmp/repaired.json" in command
    assert command[-1] == "-"


def _evidence_pack() -> EvidencePack:
    return EvidencePack(
        items=[
            EvidencePackItem(
                evidence_id="ev_1",
                source_type="codex_session",
                source_ref="codex-session-1",
                title="Agent Workflow Radar",
                summary="Repeated work on local agent session analysis.",
                raw_excerpt="Build Tradar from local agent sessions.",
                observed_at=ensure_utc_datetime("2026-05-24T08:00:00Z"),
                recurrence_count=2,
                confidence=1.0,
            )
        ],
        omitted_summary=OmittedSummary(total_omitted=0),
    )


def _prompt_assets() -> PromptAssets:
    return PromptAssets(
        analyst=load_prompt_asset("analyst", "tradar/agent_runner/prompts/analyst.md"),
        schema_repair=load_prompt_asset(
            "schema_repair",
            "tradar/agent_runner/prompts/schema_repair.md",
        ),
        html_design=load_prompt_asset(
            "html_design",
            "tradar/agent_runner/prompts/html_design.md",
        ),
    )


def _agent_output_json() -> str:
    card = {
        "title": "Agent Workflow Radar",
        "one_sentence": "Find project ideas from real agent work evidence.",
        "evidence_ids": ["ev_1", "ev_2"],
        "evidence_notes": ["Codex repeats this.", "Docs specify it."],
        "why_you": ["The user already preserves agent work."],
        "why_now": ["Recent sessions are enough."],
        "first_users": "Personal builders.",
        "demo_48h": ["Scan.", "Pack.", "Render."],
        "adjacent_products": [],
        "search_trace": {"used_search": False, "impact": "none"},
        "risks": ["Generic summaries."],
        "kill_signals": ["No accepted demo."],
    }
    return json.dumps(
        {
            "run_summary": {
                "run_id": "run_prompt_smoke",
                "generated_at": "2026-05-24T08:00:00Z",
                "timezone": "Asia/Shanghai",
                "days_window": 30,
                "evidence_count": 2,
                "warning_count": 0,
                "rendered_by": "base",
            },
            "opportunity_cards": [card],
            "decision_prompt": {
                "needs_user_confirmation": ["Confirm demo start."],
            },
        }
    )
