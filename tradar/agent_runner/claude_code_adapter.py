"""Claude Code adapter 边界。"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from tradar.agent_runner.base import (
    AgentAdapter,
    AgentAdapterExecutionError,
    AgentRawOutput,
    PromptAsset,
    PromptAssets,
    RunContext,
    ToolPolicy,
)
from tradar.agent_runner.codex_adapter import _build_prompt_input, _build_schema_repair_input
from tradar.agent_runner.schema_repair import SchemaRepairAdapter
from tradar.evidence.pack_builder import EvidencePack


class ClaudeCodeAdapter(AgentAdapter):
    def __init__(self, claude_binary: str = "claude", timeout_seconds: int = 300) -> None:
        self.claude_binary = claude_binary
        self.timeout_seconds = timeout_seconds

    def build_command(self) -> list[str]:
        return _build_claude_code_command(self.claude_binary)

    def run(
        self,
        evidence_pack: EvidencePack,
        prompt_assets: PromptAssets,
        tool_policy: ToolPolicy,
        run_context: RunContext,
    ) -> AgentRawOutput:
        output_dir = Path(run_context.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prompt_input = _build_prompt_input(evidence_pack, prompt_assets, tool_policy, run_context)
        (output_dir / "agent_prompt.md").write_text(prompt_input, encoding="utf-8")
        started = time.monotonic()
        try:
            result = subprocess.run(
                self.build_command(),
                check=False,
                capture_output=True,
                text=True,
                input=prompt_input,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentAdapterExecutionError(
                "agent.timeout",
                f"claude analyst timed out after {self.timeout_seconds} seconds",
                artifact_path=str(output_dir),
            ) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raw_stdout = result.stdout.strip()
        if raw_stdout:
            (output_dir / "agent_last_message.json").write_text(raw_stdout, encoding="utf-8")
        raw_text = _extract_claude_result_text(raw_stdout) or result.stderr.strip()
        if result.returncode != 0 or _claude_result_is_error(raw_stdout):
            message = raw_text or f"claude adapter exited non-zero: {result.returncode}"
            raise AgentAdapterExecutionError(
                "agent.execution_failed",
                message,
                artifact_path=str(output_dir),
            )
        return AgentRawOutput(
            raw_text=raw_text,
            elapsed_ms=elapsed_ms,
            search_trace_summary=_claude_trace_summary(raw_stdout),
            warnings=[],
        )


class ClaudeCodeSchemaRepairAdapter(SchemaRepairAdapter):
    def __init__(
        self,
        prompt_asset: PromptAsset,
        output_dir: str,
        claude_binary: str = "claude",
        timeout_seconds: int = 300,
    ) -> None:
        self.prompt_asset = prompt_asset
        self.output_dir = Path(output_dir)
        self.claude_binary = claude_binary
        self.timeout_seconds = timeout_seconds

    def build_command(self) -> list[str]:
        return _build_claude_code_command(self.claude_binary)

    def repair(self, raw_text: str, error_message: str) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        prompt_input = _build_schema_repair_input(self.prompt_asset, raw_text, error_message)
        (self.output_dir / "schema_repair_prompt.md").write_text(prompt_input, encoding="utf-8")
        try:
            result = subprocess.run(
                self.build_command(),
                check=False,
                capture_output=True,
                text=True,
                input=prompt_input,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentAdapterExecutionError(
                "agent.timeout",
                f"claude schema repair timed out after {self.timeout_seconds} seconds",
                artifact_path=str(self.output_dir),
            ) from exc
        raw_stdout = result.stdout.strip()
        if raw_stdout:
            (self.output_dir / "schema_repair_last_message.json").write_text(
                raw_stdout,
                encoding="utf-8",
            )
        return _extract_claude_result_text(raw_stdout) or result.stderr.strip()


def _build_claude_code_command(claude_binary: str) -> list[str]:
    return [
        claude_binary,
        "--bare",
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def _extract_claude_result_text(raw_stdout: str) -> str:
    payload = _load_claude_json(raw_stdout)
    if payload is None:
        return raw_stdout.strip()
    structured_output = payload.get("structured_output")
    if structured_output is not None:
        return json.dumps(structured_output, ensure_ascii=False)
    result = payload.get("result")
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return raw_stdout.strip()


def _claude_result_is_error(raw_stdout: str) -> bool:
    payload = _load_claude_json(raw_stdout)
    return bool(payload and payload.get("is_error"))


def _claude_trace_summary(raw_stdout: str) -> str:
    payload = _load_claude_json(raw_stdout)
    if payload is None:
        return ""
    parts = []
    session_id = payload.get("session_id")
    if session_id:
        parts.append(f"claude_session_id={session_id}")
    total_cost_usd = payload.get("total_cost_usd")
    if total_cost_usd is not None:
        parts.append(f"claude_total_cost_usd={total_cost_usd}")
    num_turns = payload.get("num_turns")
    if num_turns is not None:
        parts.append(f"claude_num_turns={num_turns}")
    duration_ms = payload.get("duration_ms")
    if duration_ms is not None:
        parts.append(f"claude_duration_ms={duration_ms}")
    return " ".join(parts)


def _load_claude_json(raw_stdout: str) -> dict[str, Any] | None:
    if not raw_stdout.strip():
        return None
    try:
        payload = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload
