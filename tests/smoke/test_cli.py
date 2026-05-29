from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

import tradar.cli.app as cli_module
from tests.unit.test_golden_checklist import _card, _pack, _report
from tradar.agent_runner.base import AgentAdapterExecutionError, AgentRawOutput
from tradar.cli.app import app
from tradar.renderer.debug_bundle import write_debug_bundle
from tradar.schemas import RawEvent

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _write_config(
    tmp_path: Path,
    codex_path: Path = None,
    output_dir: Path | None = None,
    project_root: Path | None = None,
    max_source_file_bytes: int | None = None,
) -> Path:
    config_path = tmp_path / "config.toml"
    output_dir = output_dir or (tmp_path / "runs")
    state_dir = tmp_path / "state"
    codex = codex_path or (FIXTURES / "codex")
    config_path.write_text(
        "\n".join(
            [
                f'codex_session_paths = ["{codex}"]',
                'claude_project_paths = ["{}"]'.format(FIXTURES / "claude"),
                'project_roots = ["{}"]'.format(project_root or (FIXTURES / "project_docs")),
                f'output_dir = "{output_dir}"',
                f'state_dir = "{state_dir}"',
                "days_window = 30",
                "allow_broad_root = false",
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


def test_sources_doctor_rejects_broad_project_root(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                'codex_session_paths = ["{}"]'.format(FIXTURES / "codex"),
                'claude_project_paths = ["{}"]'.format(FIXTURES / "claude"),
                'project_roots = ["/"]',
                'output_dir = "{}"'.format(tmp_path / "runs"),
                'state_dir = "{}"'.format(tmp_path / "state"),
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 1
    assert "source.broad_root_rejected" in result.output


def test_sources_doctor_reports_missing_config_with_init_next_action(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing-config.toml"

    result = CliRunner().invoke(app, ["--config", str(missing_config), "sources", "doctor"])

    assert result.exit_code == 1
    assert "P0 config.missing" in result.output
    assert "next_action=run_tradar_init_or_pass_--config" in result.output
    assert str(missing_config) in result.output


def test_init_uses_default_agent_session_paths_without_manual_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = CliRunner().invoke(app, ["--config", str(config_path), "init"])

    assert result.exit_code == 0, result.output
    config_text = config_path.read_text(encoding="utf-8")
    assert str(Path.home() / ".codex" / "sessions") in config_text
    assert str(Path.home() / ".claude" / "projects") in config_text


def test_run_reports_missing_config_before_scan_side_effects(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing-config.toml"

    result = CliRunner().invoke(app, ["--config", str(missing_config), "run", "--days", "30"])

    assert result.exit_code == 1
    assert "P0 config.missing" in result.output
    assert "next_action=run_tradar_init_or_pass_--config" in result.output
    assert "scanned_evidence=" not in result.output
    assert not (tmp_path / "state").exists()


def test_sources_doctor_warns_when_output_dir_is_inside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    output_dir = repo / "tradar-runs"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                'codex_session_paths = ["{}"]'.format(FIXTURES / "codex"),
                'claude_project_paths = ["{}"]'.format(FIXTURES / "claude"),
                f'project_roots = ["{repo}"]',
                f'output_dir = "{output_dir}"',
                'state_dir = "{}"'.format(tmp_path / "state"),
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 0, result.output
    assert "P1 source.repo_output_dir" in result.output
    assert "path 指向 output_dir" in result.output
    assert ".gitignore" in result.output
    assert str(output_dir) in result.output


def test_sources_doctor_treats_missing_project_root_as_p2(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-project-root"
    config_path = _write_config(tmp_path, project_root=missing_root)

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 0, result.output
    assert "P2 source.optional_root_missing" in result.output
    assert str(missing_root) in result.output


def test_sources_doctor_warns_when_core_source_has_no_data(tmp_path: Path) -> None:
    empty_codex = tmp_path / "empty-codex"
    empty_codex.mkdir()
    config_path = _write_config(tmp_path, codex_path=empty_codex)

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 0, result.output
    assert "P1 source.core_no_data" in result.output
    assert str(empty_codex) in result.output


def test_sources_doctor_warns_when_source_file_is_too_large(tmp_path: Path) -> None:
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

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 0, result.output
    assert "P2 source.too_large" in result.output
    assert str(large_doc) in result.output


def test_sources_doctor_rejects_unwritable_output_dir(tmp_path: Path) -> None:
    output_file = tmp_path / "runs"
    output_file.write_text("not a directory", encoding="utf-8")
    config_path = _write_config(tmp_path, output_dir=output_file)

    result = CliRunner().invoke(app, ["--config", str(config_path), "sources", "doctor"])

    assert result.exit_code == 1
    assert "P0 source.output_unwritable" in result.output
    assert str(output_file) in result.output


def test_run_rejects_unwritable_output_dir_before_scan_side_effects(tmp_path: Path) -> None:
    output_file = tmp_path / "runs"
    output_file.write_text("not a directory", encoding="utf-8")
    config_path = _write_config(tmp_path, output_dir=output_file)

    result = CliRunner().invoke(app, ["--config", str(config_path), "run", "--days", "30"])

    assert result.exit_code == 1
    assert "source.output_unwritable" in result.output
    assert "scanned_evidence=" not in result.output
    assert not (tmp_path / "state" / "tradar.sqlite").exists()


def test_scan_writes_evidence_and_watermarks_without_generating_report(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    result = CliRunner().invoke(app, ["--config", str(config_path), "scan"])

    assert result.exit_code == 0, result.output
    assert "scanned_evidence=" in result.output
    assert "scan_summary=true" in result.output
    assert "database_path=" in result.output
    assert "source.codex_session files=" in result.output
    assert "source.project_docs files=" in result.output
    assert "next_action=uv run tradar generate --days 30 --agent codex" in result.output
    state_db = tmp_path / "state" / "tradar.sqlite"
    assert state_db.exists()
    assert not (tmp_path / "runs").exists()

    with sqlite3.connect(str(state_db)) as conn:
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        watermark_count = conn.execute("SELECT COUNT(*) FROM scan_watermarks").fetchone()[0]

    assert evidence_count >= 5
    assert watermark_count >= 3


def test_scan_skips_too_large_source_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    small_doc = project_root / "README.md"
    large_doc = project_root / "docs" / "large.md"
    large_doc.parent.mkdir(parents=True)
    small_doc.write_text("# Small\nok\n", encoding="utf-8")
    large_doc.write_text("# Large\n" + ("x" * 2_000), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        project_root=project_root,
        max_source_file_bytes=1_500,
    )

    result = CliRunner().invoke(app, ["--config", str(config_path), "scan"])

    assert result.exit_code == 0, result.output
    state_db = tmp_path / "state" / "tradar.sqlite"
    with sqlite3.connect(str(state_db)) as conn:
        large_count = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE source_path = ?",
            (str(large_doc),),
        ).fetchone()[0]
        small_count = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE source_path = ?",
            (str(small_doc),),
        ).fetchone()[0]

    assert large_count == 0
    assert small_count == 1


def test_scan_project_docs_only_reads_intent_and_decision_markdown(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    for relative_path in [
        "AGENTS.md",
        "README.md",
        "CHANGELOG.md",
        "CLAUDE.md",
        "docs/plan.md",
        "notes/idea.md",
        "src/AGENTS.md",
        "src/implementation.md",
        "scratch.md",
    ]:
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# " + relative_path + "\n", encoding="utf-8")
    config_path = _write_config(tmp_path, project_root=project_root)

    result = CliRunner().invoke(app, ["--config", str(config_path), "scan"])

    assert result.exit_code == 0, result.output
    with sqlite3.connect(str(tmp_path / "state" / "tradar.sqlite")) as conn:
        rows = [
            row[0]
            for row in conn.execute(
                "SELECT source_ref FROM evidence WHERE source_type = 'project_docs'"
            ).fetchall()
        ]

    assert "AGENTS.md" in rows
    assert "README.md" in rows
    assert "CHANGELOG.md" in rows
    assert "CLAUDE.md" in rows
    assert "docs/plan.md" in rows
    assert "notes/idea.md" in rows
    assert "src/AGENTS.md" in rows
    assert "src/implementation.md" not in rows
    assert "scratch.md" not in rows


def test_scan_skips_p0_source_and_returns_nonzero_after_scanning_readable_sources(
    tmp_path: Path,
) -> None:
    missing_codex = tmp_path / "missing-codex"
    config_path = _write_config(tmp_path, codex_path=missing_codex)

    result = CliRunner().invoke(app, ["--config", str(config_path), "scan"])

    assert result.exit_code == 1
    assert "source.unreadable" in result.output
    assert "scanned_evidence=" in result.output
    state_db = tmp_path / "state" / "tradar.sqlite"
    assert state_db.exists()

    with sqlite3.connect(str(state_db)) as conn:
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        codex_watermarks = conn.execute(
            "SELECT COUNT(*) FROM scan_watermarks WHERE source_type = 'codex_session'"
        ).fetchone()[0]

    assert evidence_count > 0
    assert codex_watermarks == 0


def test_scan_passes_raw_events_through_privacy_gate(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    filtered_source_ids: list[str] = []

    class SpyPrivacyGate:
        def filter(self, event: RawEvent) -> RawEvent:
            filtered_source_ids.append(event.source_id)
            return event

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "scan"],
        obj={"privacy_gate": SpyPrivacyGate()},
    )

    assert result.exit_code == 0, result.output
    assert filtered_source_ids


def test_generate_reads_existing_store_and_does_not_rescan_sources(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    scan_result = runner.invoke(app, ["--config", str(config_path), "scan"])
    assert scan_result.exit_code == 0, scan_result.output

    missing_source_config = _write_config(tmp_path, codex_path=tmp_path / "missing-codex")
    generate_result = runner.invoke(
        app,
        ["--config", str(missing_source_config), "generate", "--days", "30"],
    )

    assert generate_result.exit_code == 0, generate_result.output
    assert "generated_report=" in generate_result.output
    report_path = _extract_output_path(generate_result.output, "generated_report=")
    assert report_path.exists()
    assert "Project Opportunity Cards" in report_path.read_text(encoding="utf-8")


def test_generate_can_open_report_after_writing(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    scan_result = runner.invoke(app, ["--config", str(config_path), "scan"])
    assert scan_result.exit_code == 0, scan_result.output
    opened_paths: list[Path] = []

    def fake_open_report(path: Path) -> str:
        opened_paths.append(path)
        return "opened"

    monkeypatch.setattr(cli_module, "_open_report", fake_open_report)

    result = runner.invoke(app, ["--config", str(config_path), "generate", "--days", "30"])

    assert result.exit_code == 0, result.output
    report_path = _extract_output_path(result.output, "generated_report=")
    assert opened_paths == [report_path]
    assert "open_report=opened" in result.output


def test_run_composes_scan_and_generate(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    result = CliRunner().invoke(app, ["--config", str(config_path), "run", "--days", "30"])

    assert result.exit_code == 0, result.output
    assert "scanned_evidence=" in result.output
    assert "generated_report=" in result.output


def test_generate_rejects_unknown_render_mode(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    scan_result = runner.invoke(app, ["--config", str(config_path), "scan"])
    assert scan_result.exit_code == 0, scan_result.output

    result = runner.invoke(
        app,
        ["--config", str(config_path), "generate", "--render", "unsupported"],
    )

    assert result.exit_code != 0
    assert "config.invalid_render_mode" in result.output
    assert "render must be base or enhanced" in result.output
    assert "next_action=use_--render_base_or_enhanced" in result.output


def test_generate_rejects_unknown_agent_mode_with_registered_event(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "generate", "--agent", "unsupported"],
    )

    assert result.exit_code == 1
    assert "config.invalid_agent_mode" in result.output
    assert "agent must be base, codex, or claude" in result.output
    assert "next_action=use_--agent_base_codex_or_claude" in result.output


def test_run_rejects_unknown_agent_mode_before_scan_side_effects(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "run", "--agent", "unsupported"],
    )

    assert result.exit_code == 1
    assert "config.invalid_agent_mode" in result.output
    assert "scanned_evidence=" not in result.output
    assert not (tmp_path / "state" / "tradar.sqlite").exists()


def test_generate_reports_agent_execution_failed_event(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    scan_result = runner.invoke(app, ["--config", str(config_path), "scan"])
    assert scan_result.exit_code == 0, scan_result.output

    class FailingAgentAdapter:
        def run(self, *args, **kwargs):
            _ = args, kwargs
            raise AgentAdapterExecutionError(
                "agent.execution_failed",
                "codex failed before producing JSON",
                artifact_path=str(tmp_path / "runs" / "run_failed"),
            )

    monkeypatch.setattr(
        cli_module,
        "_agent_adapter_for_mode",
        lambda agent_mode, agent_adapter=None, config=None: FailingAgentAdapter(),
    )

    result = runner.invoke(app, ["--config", str(config_path), "generate", "--agent", "codex"])

    assert result.exit_code == 1
    assert "agent.execution_failed" in result.output
    assert "artifact_path=" in result.output
    assert "next_action=inspect_agent_prompt_and_retry" in result.output
    assert "agent.schema_invalid" not in result.output


def test_generate_reports_schema_invalid_with_run_context(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    scan_result = runner.invoke(app, ["--config", str(config_path), "scan"])
    assert scan_result.exit_code == 0, scan_result.output

    class InvalidJsonAgentAdapter:
        def run(self, *args, **kwargs):
            _ = args, kwargs
            return AgentRawOutput(raw_text="{not valid json", elapsed_ms=1)

    monkeypatch.setattr(
        cli_module,
        "_agent_adapter_for_mode",
        lambda agent_mode, agent_adapter=None, config=None: InvalidJsonAgentAdapter(),
    )
    monkeypatch.setattr(
        cli_module,
        "_schema_repair_adapter_for_mode",
        lambda agent_mode, prompt_assets, run_context, config: None,
    )

    result = runner.invoke(app, ["--config", str(config_path), "generate", "--agent", "codex"])

    assert result.exit_code == 1
    assert "agent.schema_invalid" in result.output
    assert "run_id=run_" in result.output
    assert "artifact_path=" in result.output
    assert "next_action=inspect_agent_raw_output_and_schema_repair" in result.output


def test_golden_check_reads_run_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run_golden"
    report = _report(card=_card(evidence_ids=["ev_1", "ev_2"]))
    write_debug_bundle(
        run_dir=run_dir,
        run_record=report.run_summary,
        warnings=[],
        evidence_pack=_pack(["ev_1", "ev_2"]),
        agent_raw_output={"mode": "codex"},
        validated_report=report,
        render_log="rendered_by=base",
        report_html="<html>Run Summary</html>",
    )

    result = CliRunner().invoke(app, ["golden-check", str(run_dir)])

    assert result.exit_code == 0, result.output
    assert "golden_check_passed=true" in result.output


def test_golden_check_exits_nonzero_for_failed_checklist(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run_bad"
    report = _report(card=_card(evidence_ids=["ev_1", "ev_2"]), with_demo=False)
    run_dir.mkdir(parents=True)
    (run_dir / "validated_report.json").write_text(report.json(), encoding="utf-8")
    (run_dir / "evidence_pack.json").write_text(
        json.dumps({"items": [], "omitted_summary": {"total_omitted": 0}}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["golden-check", str(run_dir)])

    assert result.exit_code == 1
    assert "golden_check_passed=false" in result.output
    assert "this_weeks_demo.missing" in result.output


def test_decision_commands_only_write_decision_state(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    report = _report(card=_card(evidence_ids=["ev_1", "ev_2"]))
    card_id = report.opportunity_cards[0].card_id
    run_dir = tmp_path / "runs" / "run_known_card"
    run_dir.mkdir(parents=True)
    (run_dir / "validated_report.json").write_text(report.json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["--config", str(config_path), "accept", card_id])

    assert result.exit_code == 0, result.output
    state_db = tmp_path / "state" / "tradar.sqlite"
    with sqlite3.connect(str(state_db)) as conn:
        decision = conn.execute(
            "SELECT decision FROM decision_state WHERE card_id = ?",
            (card_id,),
        ).fetchone()[0]
        evidence_tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='evidence'"
        ).fetchone()[0]

    assert decision == "accept"
    assert evidence_tables == 0


def test_decision_command_rejects_unknown_card_id_without_writing_state(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    report = _report(card=_card(evidence_ids=["ev_1", "ev_2"]))
    run_dir = tmp_path / "runs" / "run_known_card"
    run_dir.mkdir(parents=True)
    (run_dir / "validated_report.json").write_text(report.json(), encoding="utf-8")

    result = CliRunner().invoke(app, ["--config", str(config_path), "reject", "card_missing"])

    assert result.exit_code == 1
    assert "decision.unknown_card_id" in result.output
    assert "card_missing" in result.output
    assert not (tmp_path / "state" / "tradar.sqlite").exists()


def _extract_output_path(output: str, prefix: str) -> Path:
    for line in output.splitlines():
        if line.startswith(prefix):
            return Path(line[len(prefix) :].strip())
    raise AssertionError("missing output prefix: " + prefix)
