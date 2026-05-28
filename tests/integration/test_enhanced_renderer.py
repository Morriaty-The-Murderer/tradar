from __future__ import annotations

import os
from pathlib import Path

from tradar.agent_runner.base import PromptAsset
from tradar.renderer.enhanced import (
    CodexHtmlEnhancer,
    EnhancedRenderResult,
    render_with_optional_enhancement,
)
from tradar.schemas import DecisionPrompt, RadarReport, RunSummary


def _empty_report() -> RadarReport:
    return RadarReport(
        run_summary=RunSummary(
            run_id="run_enhanced",
            generated_at="2026-05-24T08:00:00Z",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=0,
            warning_count=0,
            rendered_by="base",
        ),
        opportunity_cards=[],
        this_weeks_demo=None,
        decision_prompt=DecisionPrompt(
            needs_user_confirmation=["Run analyst agent before deciding."],
        ),
    )


def test_enhanced_renderer_falls_back_when_required_section_missing() -> None:
    result = render_with_optional_enhancement(
        _empty_report(),
        enhancer=lambda base_html: EnhancedRenderResult(
            html="<html><body>Run Summary</body></html>",
            elapsed_ms=12,
            warnings=[],
        ),
    )

    assert result.rendered_by == "base"
    assert "This Week's Demo" in result.html
    assert "render.enhanced_failed" in result.warnings


def test_enhanced_renderer_uses_valid_enhanced_html() -> None:
    def enhancer(base_html: str) -> EnhancedRenderResult:
        return EnhancedRenderResult(
            html=base_html.replace("rendered_by: base", "rendered_by: enhanced"),
            elapsed_ms=8,
            warnings=[],
        )

    result = render_with_optional_enhancement(_empty_report(), enhancer=enhancer)

    assert result.rendered_by == "enhanced"
    assert "rendered_by: enhanced" in result.html
    assert result.warnings == []


def test_codex_html_enhancer_streams_progress_without_timeout(tmp_path: Path) -> None:
    fake_codex = tmp_path / "fake_codex.py"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import pathlib",
                "import sys",
                "output_path = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])",
                "sys.stdin.read()",
                "events = [",
                "  {'type': 'thread.started', 'thread_id': 'thread_demo'},",
                "  {'type': 'turn.started'},",
                "  {'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'curl -s http://127.0.0.1:7456/api/health'}},",
                "  {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'curl -s http://127.0.0.1:7456/api/health', 'exit_code': 0}},",
                "  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Composed enhanced high-fidelity HTML.'}},",
                "]",
                "for event in events:",
                "    print(json.dumps(event), flush=True)",
                "output_path.write_text('<html><body>Run Summary This Week\\'s Demo Project Opportunity Cards Demo Briefs Decision Prompt</body></html>', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(fake_codex, 0o755)
    progress: list[str] = []
    enhancer = CodexHtmlEnhancer(
        prompt_asset=PromptAsset(
            name="html_design",
            path="prompt.md",
            content_hash="hash",
            content="# prompt",
        ),
        output_dir=str(tmp_path / "run"),
        codex_binary=str(fake_codex),
        progress_sink=progress.append,
    )

    result = enhancer("<html>base</html>")

    assert result.html.startswith("<html>")
    assert enhancer.timeout_seconds is None
    assert any("thread_demo" in item for item in progress)
    assert any("curl -s http://127.0.0.1:7456/api/health" in item for item in progress)
    assert any("Composed enhanced high-fidelity HTML." in item for item in progress)
    assert (tmp_path / "run" / "html_design_progress.jsonl").exists()
