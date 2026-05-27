"""Agent adapter 基础契约和 prompt asset 加载。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from tradar.evidence.pack_builder import EvidencePack


@dataclass(frozen=True)
class PromptAsset:
    name: str
    path: str
    content_hash: str
    content: str
    label: str = ""


@dataclass(frozen=True)
class PromptAssets:
    analyst: PromptAsset
    schema_repair: PromptAsset
    html_design: PromptAsset


@dataclass(frozen=True)
class ToolPolicy:
    allow_search: bool = True


@dataclass(frozen=True)
class RunContext:
    run_id: str
    output_dir: str


@dataclass(frozen=True)
class AgentRawOutput:
    raw_text: str
    elapsed_ms: int
    search_trace_summary: str = ""
    warnings: list[str] = field(default_factory=list)


class AgentAdapterExecutionError(RuntimeError):
    def __init__(self, event: str, message: str, artifact_path: str = "") -> None:
        self.event = event
        self.artifact_path = artifact_path
        super().__init__(message)


class AgentAdapter:
    def run(
        self,
        evidence_pack: EvidencePack,
        prompt_assets: PromptAssets,
        tool_policy: ToolPolicy,
        run_context: RunContext,
    ) -> AgentRawOutput:
        raise NotImplementedError


class MockAgentAdapter(AgentAdapter):
    def __init__(self, output: AgentRawOutput) -> None:
        self.output = output

    def run(
        self,
        evidence_pack: EvidencePack,
        prompt_assets: PromptAssets,
        tool_policy: ToolPolicy,
        run_context: RunContext,
    ) -> AgentRawOutput:
        return self.output


def load_prompt_asset(name: str, path: str, label: str = "") -> PromptAsset:
    prompt_path = Path(path)
    content = prompt_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return PromptAsset(
        name=name,
        path=str(prompt_path),
        content_hash=content_hash,
        content=content,
        label=label or name,
    )
