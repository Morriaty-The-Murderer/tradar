from __future__ import annotations

import json
from pathlib import Path

from tradar.cli.app import generate_report, scan_sources
from tradar.config.loader import load_config

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def test_generate_populates_run_summary_sources_and_debug_path(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    html = report_path.read_text(encoding="utf-8")
    summary = report["run_summary"]

    assert summary["sources_requested"] == [
        "claude_code_session",
        "codex_session",
        "project_docs",
    ]
    assert summary["sources_succeeded"] == [
        "claude_code_session",
        "codex_session",
        "project_docs",
    ]
    assert summary["sources_failed"] == []
    assert summary["source_scan_file_counts"]["codex_session"] >= 2
    assert summary["source_scan_file_counts"]["claude_code_session"] >= 2
    assert summary["source_scan_file_counts"]["project_docs"] >= 1
    assert summary["source_scan_elapsed_ms"]["codex_session"] >= 0
    assert summary["debug_bundle_path"] == str(run_dir)
    assert summary["config_overrides"]["agent_mode"] == "base"
    assert summary["config_overrides"]["render_mode"] == "base"
    assert summary["report_status"] == "complete"
    assert summary["next_steps"] == []
    assert summary["confidence_note"]
    assert summary["warning_events"]["connector.parse_warning"] >= 2
    assert summary["source_warning_counts"]["claude_code_session"] >= 1
    assert summary["source_warning_counts"]["codex_session"] >= 1
    assert run_record["status"] == "generated"
    assert run_record["run_id"] == summary["run_id"]
    assert run_record["run_summary"] == summary
    stored_record = _stored_run(config.database_path, summary["run_id"])
    assert stored_record["status"] == "generated"
    assert stored_record["run_summary"] == summary
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    assert warning_rows
    for row in warning_rows:
        assert row["run_id"] == summary["run_id"]
        assert row["event"]
        assert row["level"]
        assert row["source_type"]
        assert row.get("source_ref") or row.get("path")
        assert row["message"]
    assert "Sources" in html
    assert "Confidence" in html
    assert "Warning Events" in html
    assert "Source Warning Counts" in html
    assert "Source Scan Metrics" in html


def test_generate_marks_partial_when_core_source_never_succeeded(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, include_claude=False)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warnings = (run_dir / "warnings.jsonl").read_text(encoding="utf-8")
    html = report_path.read_text(encoding="utf-8")
    summary = report["run_summary"]

    assert summary["report_status"] == "partial"
    assert summary["sources_failed"] == ["claude_code_session"]
    assert "report.partial" in warnings
    assert "uv run python -m tradar.cli.app run --days 30" in summary["next_steps"]
    assert "Report Status" in html
    assert "partial" in html


def test_generate_marks_empty_without_scan_watermark(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warnings = (run_dir / "warnings.jsonl").read_text(encoding="utf-8")
    html = report_path.read_text(encoding="utf-8")
    summary = report["run_summary"]

    assert summary["report_status"] == "empty"
    assert "report.empty" in warnings
    assert "uv run python -m tradar.cli.app scan" in summary["next_steps"]
    assert "Next Steps" in html
    assert "No scan watermark found" in html


def test_generate_marks_low_confidence_when_evidence_below_threshold(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, low_confidence_evidence_threshold=10)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warnings = (run_dir / "warnings.jsonl").read_text(encoding="utf-8")
    html = report_path.read_text(encoding="utf-8")
    summary = report["run_summary"]

    assert summary["report_status"] == "low_confidence"
    assert summary["sources_failed"] == []
    assert "report.low_confidence" in warnings
    assert "uv run python -m tradar.cli.app run --days 30 --agent codex" in summary[
        "next_steps"
    ]
    assert "Report Status" in html
    assert "low_confidence" in html


def test_generate_records_p1_doctor_warnings_in_run_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    config_path = _write_config(tmp_path, output_dir=repo / "tradar-runs")
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    repo_output_warning = next(
        row for row in warning_rows if row["event"] == "source.repo_output_dir"
    )

    assert report["run_summary"]["warning_events"]["source.repo_output_dir"] == 1
    assert repo_output_warning["level"] == "warn"
    assert repo_output_warning["source_type"] == "config"
    assert repo_output_warning["path"] == str(repo / "tradar-runs")
    assert repo_output_warning["message"]


def test_generate_records_missing_optional_project_root_as_p2_warning(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-project-root"
    config_path = _write_config(tmp_path, project_root=missing_root)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    optional_root_warning = next(
        row for row in warning_rows if row["event"] == "source.optional_root_missing"
    )

    assert report["run_summary"]["warning_events"]["source.optional_root_missing"] == 1
    assert optional_root_warning["level"] == "warn"
    assert optional_root_warning["source_type"] == "project_docs"
    assert optional_root_warning["path"] == str(missing_root)
    assert optional_root_warning["message"]


def test_generate_records_core_source_no_data_as_p1_warning(tmp_path: Path) -> None:
    empty_codex = tmp_path / "empty-codex"
    empty_codex.mkdir()
    config_path = _write_config(tmp_path, codex_path=empty_codex)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    core_no_data_warning = next(
        row for row in warning_rows if row["event"] == "source.core_no_data"
    )

    assert report["run_summary"]["warning_events"]["source.core_no_data"] == 1
    assert core_no_data_warning["level"] == "warn"
    assert core_no_data_warning["source_type"] == "codex_session"
    assert core_no_data_warning["path"] == str(empty_codex)
    assert core_no_data_warning["message"]


def test_generate_records_source_evidence_below_quota_as_p2_warning(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    quota_warning = next(
        row
        for row in warning_rows
        if row["event"] == "source.evidence_below_quota"
        and row["source_type"] == "codex_session"
    )

    assert report["run_summary"]["warning_events"]["source.evidence_below_quota"] >= 1
    assert quota_warning["level"] == "warn"
    assert quota_warning["source_ref"] == "codex_session"
    assert "below source quota" in quota_warning["message"]


def test_generate_records_too_large_source_files_as_p2_warning(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    large_doc = project_root / "docs" / "large.md"
    large_doc.parent.mkdir(parents=True)
    large_doc.write_text("# Large\n" + ("x" * 2_000), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        project_root=project_root,
        max_source_file_bytes=1_500,
    )
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    run_dir = report_path.parent
    report = json.loads((run_dir / "validated_report.json").read_text(encoding="utf-8"))
    warning_rows = _jsonl_rows(run_dir / "warnings.jsonl")
    too_large_warning = next(row for row in warning_rows if row["event"] == "source.too_large")

    assert report["run_summary"]["warning_events"]["source.too_large"] == 1
    assert too_large_warning["level"] == "warn"
    assert too_large_warning["source_type"] == "project_docs"
    assert too_large_warning["path"] == str(large_doc)
    assert too_large_warning["message"]


def test_generate_applies_configured_pack_token_budget(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, max_pack_tokens=80)
    config = load_config(config_path)
    scan_sources(config)

    report_path = generate_report(config, days=30)

    pack = json.loads((report_path.parent / "evidence_pack.json").read_text(encoding="utf-8"))

    assert pack["items"]
    assert pack["omitted_summary"]["total_omitted"] > 0


def test_generate_applies_configured_debug_retention(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, debug_retention_run_count=2)
    config = load_config(config_path)
    scan_sources(config)

    first = generate_report(config, days=30).parent
    second = generate_report(config, days=30).parent
    third = generate_report(config, days=30).parent

    run_dirs = sorted(path.name for path in (tmp_path / "runs").iterdir() if path.is_dir())
    assert not first.exists()
    assert second.exists()
    assert third.exists()
    assert run_dirs == sorted([second.name, third.name])


def _write_config(
    tmp_path: Path,
    include_claude: bool = True,
    debug_retention_run_count: int = 20,
    low_confidence_evidence_threshold: int = 3,
    output_dir: Path | None = None,
    project_root: Path | None = None,
    codex_path: Path | None = None,
    max_pack_tokens: int = 24000,
    max_source_file_bytes: int | None = None,
) -> Path:
    config_path = tmp_path / "config.toml"
    claude_line = (
        'claude_project_paths = ["{}"]'.format(FIXTURES / "claude")
        if include_claude
        else "claude_project_paths = []"
    )
    config_path.write_text(
        "\n".join(
            [
                'codex_session_paths = ["{}"]'.format(codex_path or (FIXTURES / "codex")),
                claude_line,
                'project_roots = ["{}"]'.format(project_root or (FIXTURES / "project_docs")),
                'output_dir = "{}"'.format(output_dir or (tmp_path / "runs")),
                'state_dir = "{}"'.format(tmp_path / "state"),
                "days_window = 30",
                "allow_broad_root = false",
                f"debug_retention_run_count = {debug_retention_run_count}",
                f"low_confidence_evidence_threshold = {low_confidence_evidence_threshold}",
                f"max_pack_tokens = {max_pack_tokens}",
                *(
                    [f"max_source_file_bytes = {max_source_file_bytes}"]
                    if max_source_file_bytes is not None
                    else []
                ),
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _stored_run(database_path: Path, run_id: str) -> dict:
    from tradar.evidence.store import EvidenceStore

    stored = EvidenceStore(database_path).get_run(run_id)
    assert stored is not None
    return json.loads(stored.json())


def _jsonl_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
