"""可选增强 HTML 渲染路径。"""

from __future__ import annotations

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


class CodexHtmlEnhancer:
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
        started = time.monotonic()
        result = subprocess.run(
            self.build_command(output_path),
            check=False,
            capture_output=True,
            text=True,
            input=prompt_input,
            timeout=self.timeout_seconds,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            raise RuntimeError("html design agent exited non-zero")
        html = _read_output_text(output_path) or result.stdout.strip() or result.stderr.strip()
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

    html = enhanced.html.replace("rendered_by: base", "rendered_by: enhanced")
    return RenderResult(
        html=html,
        rendered_by="enhanced",
        warnings=list(enhanced.warnings),
        enhanced_elapsed_ms=enhanced.elapsed_ms,
    )


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
