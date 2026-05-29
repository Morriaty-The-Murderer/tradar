"""可选增强 HTML 渲染路径。"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tradar.agent_runner.base import PromptAsset
from tradar.renderer.base import render_base_report, validate_required_sections
from tradar.schemas import RadarReport


@dataclass(frozen=True)
class EnhancedRenderResult:
    html: str
    elapsed_ms: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderResult:
    html: str
    rendered_by: str
    warnings: list[str] = field(default_factory=list)
    enhanced_elapsed_ms: int | None = None


Enhancer = Callable[[str], EnhancedRenderResult]
ProgressSink = Callable[[str], None]


class CodexHtmlEnhancer:
    def __init__(
        self,
        prompt_asset: PromptAsset,
        output_dir: str,
        codex_binary: str = "codex",
        timeout_seconds: int | None = None,
        progress_sink: ProgressSink | None = None,
    ) -> None:
        self.prompt_asset = prompt_asset
        self.output_dir = Path(output_dir)
        self.codex_binary = codex_binary
        self.timeout_seconds = timeout_seconds
        self.progress_sink = progress_sink

    def build_command(self, output_path: str) -> list[str]:
        return [
            self.codex_binary,
            "exec",
            "--json",
            "--output-last-message",
            output_path,
            "-",
        ]

    def __call__(self, base_html: str) -> EnhancedRenderResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        prompt_input = _build_html_design_input(self.prompt_asset, base_html)
        (self.output_dir / "html_design_prompt.md").write_text(prompt_input, encoding="utf-8")
        output_path = str(self.output_dir / "html_design_last_message.html")
        progress_path = self.output_dir / "html_design_progress.jsonl"
        started = time.monotonic()
        process = subprocess.Popen(
            self.build_command(output_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(prompt_input)
        process.stdin.close()
        try:
            with progress_path.open("w", encoding="utf-8") as progress_file:
                for line in process.stdout:
                    progress_file.write(line)
                    progress_file.flush()
                    message = _codex_progress_message(line)
                    if message:
                        _emit_progress(self.progress_sink, message)
            returncode = process.wait(timeout=self.timeout_seconds)
        except BaseException:
            process.kill()
            process.wait()
            raise
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if returncode != 0:
            raise RuntimeError("html design agent exited non-zero")
        html = _read_output_text(output_path)
        return EnhancedRenderResult(html=html, elapsed_ms=elapsed_ms, warnings=[])


def render_with_optional_enhancement(
    report: RadarReport,
    enhancer: Enhancer | None = None,
) -> RenderResult:
    base_html = render_base_report(report)
    if enhancer is None:
        return RenderResult(html=base_html, rendered_by="base")

    try:
        enhanced = enhancer(base_html)
    except Exception:
        return RenderResult(
            html=base_html,
            rendered_by="base",
            warnings=["render.enhanced_failed"],
        )

    missing = validate_required_sections(enhanced.html)
    if missing:
        return RenderResult(
            html=base_html,
            rendered_by="base",
            warnings=["render.enhanced_failed"],
            enhanced_elapsed_ms=enhanced.elapsed_ms,
        )

    if _report_requires_interactive_demo(report) and not _has_interactive_demo_prototype(
        enhanced.html
    ):
        return RenderResult(
            html=base_html,
            rendered_by="base",
            warnings=["render.enhanced_static_prototype"],
            enhanced_elapsed_ms=enhanced.elapsed_ms,
        )

    html = enhanced.html.replace("rendered_by: base", "rendered_by: enhanced")
    return RenderResult(
        html=html,
        rendered_by="enhanced",
        warnings=list(enhanced.warnings),
        enhanced_elapsed_ms=enhanced.elapsed_ms,
    )


def _report_requires_interactive_demo(report: RadarReport) -> bool:
    return any(card.demo_brief is not None for card in report.opportunity_cards)


def _has_interactive_demo_prototype(html: str) -> bool:
    lowered = html.lower()
    state_markers = [
        "addeventlistener",
        "aria-pressed",
        "aria-selected",
        "classlist.toggle",
        "data-state",
        "data-active",
        "<details",
        "checked",
    ]
    return "data-demo-action" in lowered and any(marker in lowered for marker in state_markers)


def _build_html_design_input(prompt_asset: PromptAsset, base_html: str) -> str:
    return "\n\n".join(
        [
            prompt_asset.content,
            "## Base HTML",
            base_html,
            "Return only the full enhanced HTML document.",
        ]
    )


def _read_output_text(output_path: str) -> str:
    path = Path(output_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _emit_progress(progress_sink: ProgressSink | None, message: str) -> None:
    if progress_sink is not None:
        progress_sink(message)


def _codex_progress_message(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return f"[html-design] {stripped[:240]}"

    event_type = event.get("type", "")
    if event_type == "thread.started":
        return f"[html-design] started thread {event.get('thread_id', '')}".strip()
    if event_type == "turn.started":
        return "[html-design] turn started"
    if event_type != "item.started" and event_type != "item.completed":
        return ""

    item = event.get("item") or {}
    item_type = item.get("type", "")
    status = "started" if event_type == "item.started" else "completed"
    if item_type == "command_execution":
        command = str(item.get("command", "")).strip()
        exit_code = item.get("exit_code")
        if status == "completed" and exit_code is not None:
            return f"[html-design] command completed exit={exit_code}: {command}"
        return f"[html-design] command {status}: {command}"
    if item_type == "agent_message":
        text = " ".join(str(item.get("text", "")).split())
        if not text:
            return ""
        if len(text) > 240:
            text = text[:237] + "..."
        return f"[html-design] message: {text}"
    if item_type:
        return f"[html-design] {item_type} {status}"
    return ""
