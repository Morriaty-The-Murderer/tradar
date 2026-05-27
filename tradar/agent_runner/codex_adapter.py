"""Codex adapter 边界。"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from tradar.agent_runner.base import (
    AgentAdapter,
    AgentAdapterExecutionError,
    AgentRawOutput,
    PromptAsset,
    PromptAssets,
    RunContext,
    ToolPolicy,
)
from tradar.agent_runner.schema_repair import SchemaRepairAdapter
from tradar.evidence.pack_builder import EvidencePack


class CodexAdapter(AgentAdapter):
    def __init__(self, codex_binary: str = "codex", timeout_seconds: int = 300) -> None:
        self.codex_binary = codex_binary
        self.timeout_seconds = timeout_seconds

    def build_command(self, prompt_path: str, output_path: str) -> list[str]:
        _ = prompt_path
        return _build_codex_exec_command(self.codex_binary, output_path)

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
        output_path = str(output_dir / "agent_last_message.json")
        command = self.build_command(prompt_assets.analyst.path, output_path)
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                input=prompt_input,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentAdapterExecutionError(
                "agent.timeout",
                f"codex analyst timed out after {self.timeout_seconds} seconds",
                artifact_path=str(output_dir),
            ) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raw_text = _read_output_text(output_path) or result.stdout.strip() or result.stderr.strip()
        if result.returncode != 0:
            message = raw_text or f"codex adapter exited non-zero: {result.returncode}"
            raise AgentAdapterExecutionError(
                "agent.execution_failed",
                message,
                artifact_path=str(output_dir),
            )
        warnings = [] if result.returncode == 0 else ["codex adapter exited non-zero"]
        return AgentRawOutput(raw_text=raw_text, elapsed_ms=elapsed_ms, warnings=warnings)


class CodexSchemaRepairAdapter(SchemaRepairAdapter):
    def __init__(
        self,
        prompt_asset: PromptAsset,
        output_dir: str,
        codex_binary: str = "codex",
        timeout_seconds: int = 300,
    ) -> None:
        self.prompt_asset = prompt_asset
        self.output_dir = Path(output_dir)
        self.codex_binary = codex_binary
        self.timeout_seconds = timeout_seconds

    def build_command(self, output_path: str) -> list[str]:
        return _build_codex_exec_command(self.codex_binary, output_path)

    def repair(self, raw_text: str, error_message: str) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(self.output_dir / "schema_repair_last_message.json")
        prompt_input = _build_schema_repair_input(self.prompt_asset, raw_text, error_message)
        (self.output_dir / "schema_repair_prompt.md").write_text(prompt_input, encoding="utf-8")
        try:
            result = subprocess.run(
                self.build_command(output_path),
                check=False,
                capture_output=True,
                text=True,
                input=prompt_input,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentAdapterExecutionError(
                "agent.timeout",
                f"codex schema repair timed out after {self.timeout_seconds} seconds",
                artifact_path=str(self.output_dir),
            ) from exc
        return _read_output_text(output_path) or result.stdout.strip() or result.stderr.strip()


def _build_codex_exec_command(codex_binary: str, output_path: str) -> list[str]:
    return [
        codex_binary,
        "exec",
        "--json",
        "--output-last-message",
        output_path,
        "-",
    ]


def _build_prompt_input(
    evidence_pack: EvidencePack,
    prompt_assets: PromptAssets,
    tool_policy: ToolPolicy,
    run_context: RunContext,
) -> str:
    payload = {
        "run_context": {
            "run_id": run_context.run_id,
            "tool_policy": {"allow_search": tool_policy.allow_search},
        },
        "evidence_pack": {
            "items": [
                {
                    "evidence_id": item.evidence_id,
                    "source_type": item.source_type,
                    "source_ref": item.source_ref,
                    "title": item.title,
                    "summary": item.summary,
                    "observed_at": item.observed_at.isoformat(),
                    "recurrence_count": item.recurrence_count,
                    "confidence": item.confidence,
                }
                for item in evidence_pack.items
            ],
            "omitted_summary": {
                "total_omitted": evidence_pack.omitted_summary.total_omitted,
                "by_source_type": evidence_pack.omitted_summary.by_source_type,
            },
        },
    }
    return "\n\n".join(
        [
            prompt_assets.analyst.content,
            "## Runtime Contract",
            "Return only JSON that matches the RadarReport schema.",
            "Use only evidence_id values present in the evidence pack.",
            "## Evidence Pack JSON",
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )


def _build_schema_repair_input(
    prompt_asset: PromptAsset,
    raw_text: str,
    error_message: str,
) -> str:
    return "\n\n".join(
        [
            prompt_asset.content,
            "## Validation Error",
            error_message,
            "## Invalid Analyst Output",
            raw_text,
            "Return only repaired RadarReport JSON.",
        ]
    )


def _read_output_text(output_path: str) -> str:
    path = Path(output_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
