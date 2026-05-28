from __future__ import annotations

import json
from pathlib import Path

import tradar.cli.app as cli_module
from tradar.cli.app import generate_report, scan_sources
from tradar.config.loader import load_config
from tradar.errors.catalog import ERROR_CATALOG
from tradar.renderer.enhanced import EnhancedRenderResult

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def test_generate_with_enhanced_render_writes_enhanced_artifacts(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(
        config,
        days=30,
        render_mode="enhanced",
        html_enhancer=lambda base_html: EnhancedRenderResult(
            html=base_html.replace("rendered_by: base", "rendered_by: enhanced"),
            elapsed_ms=15,
            warnings=[],
        ),
    )

    run_dir = report_path.parent
    validated_report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    render_log = (run_dir / "render.log").read_text(encoding="utf-8")
    html = report_path.read_text(encoding="utf-8")

    assert validated_report["run_summary"]["rendered_by"] == "enhanced"
    assert validated_report["run_summary"]["enhanced_elapsed_ms"] == 15
    assert "rendered_by=enhanced" in render_log
    assert "enhanced_elapsed_ms=15" in render_log
    assert "rendered_by: enhanced" in html


def test_generate_with_invalid_enhanced_html_falls_back_to_base(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(
        config,
        days=30,
        render_mode="enhanced",
        html_enhancer=lambda base_html: EnhancedRenderResult(
            html="<html><body>Run Summary</body></html>",
            elapsed_ms=9,
            warnings=["html_design.incomplete"],
        ),
    )

    run_dir = report_path.parent
    validated_report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = [
        json.loads(line)
        for line in (run_dir / "warnings.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    html = report_path.read_text(encoding="utf-8")
    render_warning = next(row for row in warning_rows if row["event"] == "render.enhanced_failed")
    warning_events = {row["event"] for row in warning_rows}

    assert validated_report["run_summary"]["rendered_by"] == "base"
    assert warning_events <= set(ERROR_CATALOG)
    assert render_warning["run_id"] == validated_report["run_summary"]["run_id"]
    assert render_warning["source_type"] == "renderer"
    assert render_warning["source_ref"] == "enhanced_html"
    assert render_warning["message"]
    assert "This Week's Demo" in html
    assert "rendered_by: base" in html


def test_generate_wires_html_design_progress_sink_without_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(
        tmp_path,
        html_design_timeout_seconds=14,
        codex_binary="/opt/bin/codex-preview",
    )
    config = load_config(config_path)
    scan_sources(config)
    captured: dict[str, object] = {}

    class RecordingHtmlEnhancer:
        def __init__(
            self,
            codex_binary: str = "codex",
            timeout_seconds: int | None = None,
            **kwargs,
        ) -> None:
            captured["codex_binary"] = codex_binary
            captured["html_design_timeout_seconds"] = timeout_seconds
            captured["progress_sink"] = kwargs["progress_sink"]

        def __call__(self, base_html: str) -> EnhancedRenderResult:
            captured["progress_sink"]("[html-design] test progress")
            return EnhancedRenderResult(
                html=base_html.replace("rendered_by: base", "rendered_by: enhanced"),
                elapsed_ms=1,
                warnings=[],
            )

    monkeypatch.setattr(cli_module, "CodexHtmlEnhancer", RecordingHtmlEnhancer)

    generate_report(config, days=30, render_mode="enhanced")

    assert captured["codex_binary"] == "/opt/bin/codex-preview"
    assert captured["html_design_timeout_seconds"] is None
    assert callable(captured["progress_sink"])
    progress_logs = list((tmp_path / "runs").glob("run_*/html_design_progress.log"))
    assert len(progress_logs) == 1
    assert "[html-design] test progress" in progress_logs[0].read_text(encoding="utf-8")


def _write_config(
    tmp_path: Path,
    html_design_timeout_seconds: int | None = None,
    codex_binary: str | None = None,
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
                *(
                    [f"html_design_timeout_seconds = {html_design_timeout_seconds}"]
                    if html_design_timeout_seconds is not None
                    else []
                ),
                *([f'codex_binary = "{codex_binary}"'] if codex_binary is not None else []),
            ]
        ),
        encoding="utf-8",
    )
    return config_path
