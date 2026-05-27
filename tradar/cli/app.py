"""Tradar CLI。"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from typing import cast

import typer

from tradar.agent_runner.base import (
    AgentAdapter,
    AgentAdapterExecutionError,
    AgentRawOutput,
    PromptAssets,
    RunContext,
    ToolPolicy,
    load_prompt_asset,
)
from tradar.agent_runner.codex_adapter import CodexAdapter, CodexSchemaRepairAdapter
from tradar.agent_runner.schema_repair import (
    AgentOutputSchemaError,
    SchemaRepairAdapter,
    validate_or_repair_report,
)
from tradar.config.defaults import DEFAULT_CONFIG_PATH
from tradar.config.loader import RadarConfig, load_config, write_default_config
from tradar.connectors.claude_code import parse_claude_code_session
from tradar.connectors.codex import parse_codex_session
from tradar.connectors.git_commits import parse_git_commit_line
from tradar.connectors.project_docs import parse_project_doc
from tradar.errors.catalog import get_event_definition
from tradar.evidence.normalizer import normalize_raw_event
from tradar.evidence.pack_builder import (
    DEFAULT_MIN_PER_SOURCE,
    EvidencePack,
    OmittedSummary,
    build_evidence_pack,
)
from tradar.evidence.privacy import PrivacyGate, PrivacyGateProtocol
from tradar.evidence.store import EvidenceStore
from tradar.golden.checklist import evaluate_golden_report, load_evidence_pack
from tradar.renderer.debug_bundle import apply_debug_retention, write_debug_bundle
from tradar.renderer.enhanced import (
    CodexHtmlEnhancer,
    Enhancer,
    RenderResult,
    render_with_optional_enhancement,
)
from tradar.schemas import (
    DecisionPrompt,
    DecisionState,
    RadarReport,
    RawEvent,
    RunRecord,
    RunSummary,
    generate_card_id,
)
from tradar.schemas.time import utc_now
from tradar.state.decisions import DecisionStateStore

app = typer.Typer(no_args_is_help=True)
sources_app = typer.Typer(no_args_is_help=True)
app.add_typer(sources_app, name="sources")

_CLI_STATE: dict[str, Path] = {"config_path": DEFAULT_CONFIG_PATH}
_PROMPT_DIR = Path(__file__).resolve().parents[1] / "agent_runner" / "prompts"


@dataclass(frozen=True)
class DoctorIssue:
    severity: str
    event: str
    message: str
    path: Path | None = None
    source_type: str = "config"
    source_ref: str | None = None


@dataclass(frozen=True)
class SourceHealth:
    report_status: str
    requested: list[str]
    succeeded: list[str]
    failed: list[str]
    warnings: list[dict[str, str]]
    next_steps: list[str]
    status_notes: list[str]
    warning_events: dict[str, int]
    source_warning_counts: dict[str, int]
    source_scan_file_counts: dict[str, int]
    source_scan_elapsed_ms: dict[str, int]


class CliUsageError(ValueError):
    def __init__(self, event: str, next_action: str) -> None:
        self.event = event
        self.next_action = next_action
        super().__init__(get_event_definition(event).default_user_message)


@app.callback()
def main(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", help="用户级配置路径。"),
) -> None:
    _CLI_STATE["config_path"] = Path(config).expanduser()


@app.command("init")
def init_command(
    codex_session_path: Path | None = typer.Option(None, "--codex-session-path"),
    claude_project_path: Path | None = typer.Option(None, "--claude-project-path"),
    project_root: Path | None = typer.Option(None, "--project-root"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    config_path = _config_path()
    write_default_config(
        config_path=config_path,
        codex_session_paths=[codex_session_path] if codex_session_path else [],
        claude_project_paths=[claude_project_path] if claude_project_path else [],
        project_roots=[project_root] if project_root else [],
        output_dir=output_dir,
        state_dir=state_dir,
    )
    typer.echo(f"config_written={config_path}")
    issues = doctor_config(load_config(config_path))
    _print_doctor_issues(issues)


@sources_app.command("doctor")
def sources_doctor_command() -> None:
    try:
        config = load_config(_config_path())
    except FileNotFoundError as exc:
        typer.echo(f"P0 source.unreadable {exc}")
        raise typer.Exit(1) from exc

    issues = doctor_config(config)
    _print_doctor_issues(issues)
    if any(issue.severity == "P0" for issue in issues):
        raise typer.Exit(1)


@app.command("scan")
def scan_command(ctx: typer.Context) -> None:
    config = load_config(_config_path())
    issues = doctor_config(config)
    p0_issues = [issue for issue in issues if issue.severity == "P0"]
    blocking_p0_issues = [issue for issue in p0_issues if not _scan_can_skip_issue(issue)]
    if blocking_p0_issues:
        _print_doctor_issues(blocking_p0_issues)
        raise typer.Exit(1)
    skippable_p0_issues = [issue for issue in p0_issues if _scan_can_skip_issue(issue)]
    if skippable_p0_issues:
        _print_doctor_issues(skippable_p0_issues)

    scanned = scan_sources(
        config,
        privacy_gate=_privacy_gate_from_context(ctx),
        skip_paths=[issue.path for issue in skippable_p0_issues if issue.path is not None],
    )
    typer.echo(f"scanned_evidence={scanned}")
    if skippable_p0_issues:
        raise typer.Exit(1)


@app.command("generate")
def generate_command(
    days: int | None = typer.Option(None, "--days"),
    agent: str = typer.Option("base", "--agent", help="base 或 codex。"),
    render: str = typer.Option("base", "--render", help="base 或 enhanced。"),
) -> None:
    config = load_config(_config_path())
    try:
        agent_mode = _require_agent_mode(agent)
        render_mode = _require_render_mode(render)
    except CliUsageError as exc:
        _print_cli_usage_error(exc)
        raise typer.Exit(1) from exc
    try:
        report_path = generate_report(
            config,
            days=days or config.days_window,
            agent_mode=agent_mode,
            render_mode=render_mode,
        )
    except AgentAdapterExecutionError as exc:
        _print_agent_execution_error(exc)
        raise typer.Exit(1) from exc
    except AgentOutputSchemaError as exc:
        _print_agent_schema_error(exc)
        raise typer.Exit(1) from exc
    typer.echo(f"generated_report={report_path}")


@app.command("run")
def run_command(
    ctx: typer.Context,
    days: int | None = typer.Option(None, "--days"),
    agent: str = typer.Option("base", "--agent", help="base 或 codex。"),
    render: str = typer.Option("base", "--render", help="base 或 enhanced。"),
) -> None:
    config = load_config(_config_path())
    try:
        agent_mode = _require_agent_mode(agent)
        render_mode = _require_render_mode(render)
    except CliUsageError as exc:
        _print_cli_usage_error(exc)
        raise typer.Exit(1) from exc
    issues = doctor_config(config)
    p0_issues = [issue for issue in issues if issue.severity == "P0"]
    if p0_issues:
        _print_doctor_issues(p0_issues)
        raise typer.Exit(1)
    scanned = scan_sources(config, privacy_gate=_privacy_gate_from_context(ctx))
    typer.echo(f"scanned_evidence={scanned}")
    try:
        report_path = generate_report(
            config,
            days=days or config.days_window,
            agent_mode=agent_mode,
            render_mode=render_mode,
        )
    except AgentAdapterExecutionError as exc:
        _print_agent_execution_error(exc)
        raise typer.Exit(1) from exc
    except AgentOutputSchemaError as exc:
        _print_agent_schema_error(exc)
        raise typer.Exit(1) from exc
    typer.echo(f"generated_report={report_path}")


@app.command("accept")
def accept_command(card_id: str) -> None:
    _save_decision(card_id, "accept")


@app.command("snooze")
def snooze_command(card_id: str) -> None:
    _save_decision(card_id, "snooze")


@app.command("reject")
def reject_command(card_id: str) -> None:
    _save_decision(card_id, "reject")


@app.command("golden-check")
def golden_check_command(run_dir: Path) -> None:
    report_path = run_dir / "validated_report.json"
    pack_path = run_dir / "evidence_pack.json"
    report = RadarReport.parse_raw(report_path.read_text(encoding="utf-8"))
    pack = load_evidence_pack(pack_path)
    result = evaluate_golden_report(report, pack)

    typer.echo(f"golden_check_passed={str(result.passed).lower()}")
    for failure in result.failures:
        typer.echo("FAIL " + failure)
    for manual_check in result.manual_checks:
        typer.echo("MANUAL " + manual_check)
    if not result.passed:
        raise typer.Exit(1)


def doctor_config(config: RadarConfig) -> list[DoctorIssue]:
    issues: list[DoctorIssue] = []
    if _output_dir_unwritable(config.output_dir):
        issues.append(
            DoctorIssue(
                severity="P0",
                event="source.output_unwritable",
                message=get_event_definition("source.output_unwritable").default_user_message,
                path=config.output_dir,
            )
        )
    if _repo_root_containing(config.output_dir) is not None:
        issues.append(
            DoctorIssue(
                severity="P1",
                event="source.repo_output_dir",
                message=get_event_definition("source.repo_output_dir").default_user_message,
                path=config.output_dir,
                source_type="config",
            )
        )

    issues.extend(_core_no_data_issues("codex_session", config.codex_session_paths))
    issues.extend(_core_no_data_issues("claude_code_session", config.claude_project_paths))
    issues.extend(_too_large_source_issues(config))

    for root in config.project_roots:
        if _is_broad_root(root) and not config.allow_broad_root:
            issues.append(
                DoctorIssue(
                    severity="P0",
                    event="source.broad_root_rejected",
                    message=get_event_definition("source.broad_root_rejected").default_user_message,
                    path=root,
                )
            )

    for root in config.project_roots:
        if not root.exists():
            issues.append(
                DoctorIssue(
                    severity="P2",
                    event="source.optional_root_missing",
                    message=get_event_definition("source.optional_root_missing").default_user_message,
                    path=root,
                    source_type="project_docs",
                )
            )

    for path in config.codex_session_paths + config.claude_project_paths:
        if not path.exists():
            issues.append(
                DoctorIssue(
                    severity="P0",
                    event="source.unreadable",
                    message=get_event_definition("source.unreadable").default_user_message,
                    path=path,
                )
            )
    return issues


def _too_large_source_issues(config: RadarConfig) -> list[DoctorIssue]:
    definition = get_event_definition("source.too_large")
    issues: list[DoctorIssue] = []
    for source_type, source_paths in (
        ("codex_session", config.codex_session_paths),
        ("claude_code_session", config.claude_project_paths),
    ):
        for source_path in source_paths:
            if not source_path.exists():
                continue
            for path in _jsonl_files(source_path):
                if _file_too_large(path, config.max_source_file_bytes):
                    issues.append(
                        DoctorIssue(
                            severity=definition.severity,
                            event=definition.event,
                            message=definition.default_user_message,
                            path=path,
                            source_type=source_type,
                        )
                    )

    for root in config.project_roots:
        if not root.exists() or (_is_broad_root(root) and not config.allow_broad_root):
            continue
        for path in _project_doc_files(root):
            if _file_too_large(path, config.max_source_file_bytes):
                issues.append(
                    DoctorIssue(
                        severity=definition.severity,
                        event=definition.event,
                        message=definition.default_user_message,
                        path=path,
                        source_type="project_docs",
                    )
                )
    return issues


def _core_no_data_issues(source_type: str, paths: Sequence[Path]) -> list[DoctorIssue]:
    definition = get_event_definition("source.core_no_data")
    if not paths:
        return [
            DoctorIssue(
                severity=definition.severity,
                event=definition.event,
                message=definition.default_user_message,
                source_type=source_type,
                source_ref=source_type,
            )
        ]

    issues: list[DoctorIssue] = []
    for path in paths:
        if not path.exists():
            continue
        if not _jsonl_files(path):
            issues.append(
                DoctorIssue(
                    severity=definition.severity,
                    event=definition.event,
                    message=definition.default_user_message,
                    path=path,
                    source_type=source_type,
                )
            )
    return issues


def scan_sources(
    config: RadarConfig,
    privacy_gate: PrivacyGateProtocol | None = None,
    skip_paths: Sequence[Path] | None = None,
) -> int:
    store = EvidenceStore(config.database_path)
    store.initialize()
    scanned_at = utc_now()
    total = 0
    gate = privacy_gate or PrivacyGate()

    for (
        source_type,
        source_ref,
        raw_events,
        file_count,
        elapsed_ms,
    ) in _iter_source_events(config, skip_paths=skip_paths):
        evidence_delta = 0
        warning_delta = 0
        for event in raw_events:
            filtered_event = gate.filter(event)
            evidence = normalize_raw_event(filtered_event, observed_at=scanned_at)
            store.upsert_evidence(evidence)
            evidence_delta += 1
            warning_delta += len(filtered_event.parse_warnings)
        store.record_scan_watermark(
            source_type=source_type,
            source_ref=source_ref,
            scanned_at=scanned_at,
            evidence_count_delta=evidence_delta,
            warning_count_delta=warning_delta,
            scan_status="success",
            file_count_delta=file_count,
            elapsed_ms=elapsed_ms,
        )
        total += evidence_delta
    return total


def _scan_can_skip_issue(issue: DoctorIssue) -> bool:
    return issue.path is not None and issue.event in {
        "source.unreadable",
        "source.broad_root_rejected",
    }


def generate_report(
    config: RadarConfig,
    days: int,
    agent_mode: str = "base",
    render_mode: str = "base",
    agent_adapter: AgentAdapter | None = None,
    repair_adapter: SchemaRepairAdapter | None = None,
    html_enhancer: Enhancer | None = None,
) -> Path:
    agent_mode = _require_agent_mode(agent_mode)
    render_mode = _require_render_mode(render_mode)
    if days < 1:
        raise ValueError("days must be positive")
    store = EvidenceStore(config.database_path)
    store.initialize()
    since = utc_now() - timedelta(days=days)
    evidence = store.list_evidence_since(since)
    run_id = _new_run_id()
    run_dir = config.output_dir / run_id
    pack = (
        build_evidence_pack(
            evidence,
            max_evidence_items=config.max_evidence_items,
            max_pack_tokens=config.max_pack_tokens,
        )
        if evidence
        else EvidencePack(
            items=[],
            omitted_summary=OmittedSummary(total_omitted=0),
        )
    )
    source_health = _source_health(config, store, evidence)
    warnings = list(source_health.warnings)
    agent_artifact: dict[str, object]
    prompt_assets: PromptAssets | None = None
    raw_output: AgentRawOutput | None = None
    repair_trace: _SchemaRepairTrace | None = None
    if agent_mode == "base" or not evidence:
        report = _report_from_pack(config, pack, days, len(evidence), len(warnings), run_id)
        agent_artifact = {
            "mode": "base",
            "status": "not_requested" if agent_mode == "base" else "skipped_empty_evidence",
        }
    else:
        prompt_assets = _load_prompt_assets()
        adapter = _agent_adapter_for_mode(agent_mode, agent_adapter, config)
        run_context = RunContext(run_id=run_id, output_dir=str(run_dir))
        raw_output = adapter.run(
            evidence_pack=pack,
            prompt_assets=prompt_assets,
            tool_policy=ToolPolicy(allow_search=True),
            run_context=run_context,
        )
        active_repair_adapter = repair_adapter or _schema_repair_adapter_for_mode(
            agent_mode,
            prompt_assets,
            run_context,
            config,
        )
        repair_trace = (
            _SchemaRepairTrace(active_repair_adapter) if active_repair_adapter is not None else None
        )
        try:
            report = validate_or_repair_report(
                raw_output.raw_text,
                repair_adapter=repair_trace,
            )
            _validate_report_evidence_ids(report, pack)
        except AgentOutputSchemaError as exc:
            raise AgentOutputSchemaError(
                str(exc),
                run_id=run_id,
                artifact_path=str(run_dir),
            ) from exc
        report = _normalize_opportunity_cards(report, pack, config.database_path)
        agent_artifact = _agent_raw_artifact(raw_output, prompt_assets, agent_mode)

    report = _with_runtime_summary(
        report=report,
        config=config,
        run_id=run_id,
        run_dir=run_dir,
        days=days,
        evidence_count=len(evidence),
        warning_count=len(warnings),
        agent_mode=agent_mode,
        render_mode=render_mode,
        prompt_assets=prompt_assets,
        source_health=source_health,
        raw_output=raw_output,
        repair_trace=repair_trace,
    )
    enhancer = _html_enhancer_for_mode(render_mode, prompt_assets, run_dir, html_enhancer, config)
    render_result = render_with_optional_enhancement(report, enhancer=enhancer)
    report = _with_rendered_by(report, render_result.rendered_by, render_result.enhanced_elapsed_ms)
    warnings.extend(_render_warning_rows(render_result.warnings))
    warning_rows = _with_warning_run_id(warnings, run_id)
    html = render_result.html
    run_record = RunRecord(
        run_id=report.run_summary.run_id,
        status="generated",
        run_summary=report.run_summary,
        warnings=[warning["event"] for warning in warning_rows],
    )
    write_debug_bundle(
        run_dir=run_dir,
        run_record=run_record,
        warnings=warning_rows,
        evidence_pack=pack,
        agent_raw_output=agent_artifact,
        validated_report=report,
        render_log=_render_log(render_result),
        report_html=html,
        save_agent_raw_output=config.save_agent_raw_output,
    )
    store.record_run(run_record)
    deleted_run_dirs = apply_debug_retention(
        config.output_dir,
        retain_count=config.debug_retention_run_count,
    )
    if deleted_run_dirs:
        (run_dir / "retention.log").write_text(
            "\n".join(f"deleted={path}" for path in deleted_run_dirs) + "\n",
            encoding="utf-8",
        )
    return run_dir / "report.html"


def _iter_source_events(
    config: RadarConfig,
    skip_paths: Sequence[Path] | None = None,
) -> Iterable[tuple[str, str, list[RawEvent], int, int]]:
    skipped = _normalized_paths(skip_paths or [])
    for source_path in config.codex_session_paths:
        if _normalized_path(source_path) in skipped:
            continue
        started = perf_counter()
        files = _jsonl_files(source_path, max_source_file_bytes=config.max_source_file_bytes)
        raw_events = [parse_codex_session(path) for path in files]
        yield "codex_session", str(source_path), raw_events, len(files), _elapsed_ms(started)

    for source_path in config.claude_project_paths:
        if _normalized_path(source_path) in skipped:
            continue
        started = perf_counter()
        files = _jsonl_files(source_path, max_source_file_bytes=config.max_source_file_bytes)
        raw_events = [parse_claude_code_session(path) for path in files]
        yield (
            "claude_code_session",
            str(source_path),
            raw_events,
            len(files),
            _elapsed_ms(started),
        )

    for root in config.project_roots:
        if _normalized_path(root) in skipped:
            continue
        started = perf_counter()
        doc_paths = _project_doc_files(root, max_source_file_bytes=config.max_source_file_bytes)
        docs = [parse_project_doc(path, root=root) for path in doc_paths]
        yield "project_docs", str(root), docs, len(doc_paths), _elapsed_ms(started)
        started = perf_counter()
        commit_lines = _git_commit_lines(root)
        commits = [parse_git_commit_line(line, repo_path=str(root)) for line in commit_lines]
        if commits:
            yield "git_commit", str(root), commits, len(commit_lines), _elapsed_ms(started)


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _normalized_paths(paths: Sequence[Path]) -> set[str]:
    return {_normalized_path(path) for path in paths}


def _normalized_path(path: Path) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def _jsonl_files(path: Path, max_source_file_bytes: int | None = None) -> list[Path]:
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.rglob("*.jsonl"))
    return _within_size_limit(files, max_source_file_bytes)


def _project_doc_files(root: Path, max_source_file_bytes: int | None = None) -> list[Path]:
    deny_parts = {".git", "node_modules", "vendor", "dist", "build"}
    allowed_names = {"AGENTS.md", "README.md", "CHANGELOG.md", "CLAUDE.md"}
    allowed_doc_dirs = {"docs", "notes"}
    candidates: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        relative_parts = path.relative_to(root).parts
        if any(part in deny_parts for part in relative_parts):
            continue
        if path.is_symlink():
            continue
        if path.name not in allowed_names and not (
            relative_parts and relative_parts[0] in allowed_doc_dirs
        ):
            continue
        candidates.append(path)
    return _within_size_limit(candidates, max_source_file_bytes)


def _within_size_limit(
    paths: Sequence[Path],
    max_source_file_bytes: int | None,
) -> list[Path]:
    if max_source_file_bytes is None:
        return list(paths)
    return [path for path in paths if not _file_too_large(path, max_source_file_bytes)]


def _file_too_large(path: Path, max_source_file_bytes: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size > max_source_file_bytes
    except OSError:
        return False


def _git_commit_lines(root: Path) -> list[str]:
    if not (root / ".git").exists():
        return []
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "log",
            "--since=30 days ago",
            "--pretty=format:%h%x09%ad%x09%s",
            "--date=short",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _generate_warnings(
    watermarks: Sequence[dict[str, object]],
    evidence: Sequence[object],
    failed_core_sources: Sequence[str],
    low_confidence_threshold: int,
    requested_sources: Sequence[str],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for source_type, count in _source_warning_counts(watermarks).items():
        warnings.append(
            {
                "event": "connector.parse_warning",
                "level": "warn",
                "source_type": source_type,
                "source_ref": ", ".join(_source_refs_for_type(watermarks, source_type)),
                "message": f"{source_type} parse warnings: {count}",
            }
        )
    if not watermarks:
        warnings.append(
            {
                "event": "report.empty",
                "level": "warn",
                "source_type": "scan_watermark",
                "source_ref": "all_sources",
                "message": "No scan watermark found.",
            }
        )
    if not evidence:
        warnings.append(
            {
                "event": "report.empty",
                "level": "warn",
                "source_type": "evidence_store",
                "source_ref": "days_window",
                "message": "No evidence found.",
            }
        )
    if failed_core_sources and watermarks and evidence:
        warnings.append(
            {
                "event": "report.partial",
                "level": "warn",
                "source_type": "core_sources",
                "source_ref": ", ".join(failed_core_sources),
                "message": "Core source missing or failed: " + ", ".join(failed_core_sources),
            }
        )
    if watermarks and evidence and len(evidence) < low_confidence_threshold:
        warnings.append(
            {
                "event": "report.low_confidence",
                "level": "warn",
                "source_type": "evidence_pack",
                "source_ref": "days_window",
                "message": (
                    f"Evidence count {len(evidence)} is below "
                    f"low-confidence threshold {low_confidence_threshold}."
                ),
            }
        )
    warnings.extend(_source_quota_warnings(evidence, requested_sources))
    return warnings


def _source_quota_warnings(
    evidence: Sequence[object],
    requested_sources: Sequence[str],
) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    for item in evidence:
        source_type = str(getattr(item, "source_type", ""))
        if source_type:
            counts[source_type] = counts.get(source_type, 0) + 1

    warnings: list[dict[str, str]] = []
    for source_type in sorted(set(requested_sources)):
        quota = DEFAULT_MIN_PER_SOURCE.get(source_type)
        count = counts.get(source_type, 0)
        if quota is None or count == 0 or count >= quota:
            continue
        warnings.append(
            {
                "event": "source.evidence_below_quota",
                "level": "warn",
                "source_type": source_type,
                "source_ref": source_type,
                "message": f"{source_type} evidence count {count} is below source quota {quota}.",
            }
        )
    return warnings


def _source_refs_for_type(
    watermarks: Sequence[dict[str, object]],
    source_type: str,
) -> list[str]:
    refs = {
        str(row["source_ref"])
        for row in watermarks
        if str(row["source_type"]) == source_type and _int_value(row.get("warning_count_delta")) > 0
    }
    return sorted(refs)


def _source_health(
    config: RadarConfig,
    store: EvidenceStore,
    evidence: Sequence[object],
) -> SourceHealth:
    watermarks = store.list_scan_watermarks()
    core_sources = {"codex_session", "claude_code_session"}
    requested = sorted(
        {str(row["source_type"]) for row in watermarks}
        | core_sources
        | ({"project_docs"} if config.project_roots else set())
    )
    succeeded = sorted(
        {str(row["source_type"]) for row in watermarks if row.get("scan_status") == "success"}
    )
    failed_from_watermarks = {
        str(row["source_type"]) for row in watermarks if row.get("scan_status") != "success"
    }
    failed_core_sources = sorted(core_sources - set(succeeded))
    failed = sorted(failed_from_watermarks | set(failed_core_sources))
    warnings = _generate_warnings(
        watermarks,
        evidence,
        failed_core_sources,
        config.low_confidence_evidence_threshold,
        requested,
    )
    warnings.extend(_doctor_warning_rows(doctor_config(config)))
    source_warning_counts = _source_warning_counts(watermarks)

    if not watermarks or not evidence:
        report_status = "empty"
    elif failed_core_sources:
        report_status = "partial"
    elif len(evidence) < config.low_confidence_evidence_threshold:
        report_status = "low_confidence"
    else:
        report_status = "complete"

    return SourceHealth(
        report_status=report_status,
        requested=requested,
        succeeded=succeeded,
        failed=failed,
        warnings=warnings,
        next_steps=_next_steps_for_status(report_status),
        status_notes=[warning["message"] for warning in warnings],
        warning_events=_warning_event_counts(warnings, source_warning_counts),
        source_warning_counts=source_warning_counts,
        source_scan_file_counts=_source_scan_counts(watermarks, "file_count_delta"),
        source_scan_elapsed_ms=_source_scan_counts(watermarks, "elapsed_ms"),
    )


def _doctor_warning_rows(issues: Sequence[DoctorIssue]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for issue in issues:
        if issue.severity == "P0":
            continue
        row = {
            "event": issue.event,
            "level": "warn",
            "source_type": issue.source_type,
            "message": issue.message,
        }
        if issue.path is not None:
            row["path"] = str(issue.path)
        else:
            row["source_ref"] = issue.source_ref or "config"
        rows.append(row)
    return rows


def _source_warning_counts(watermarks: Sequence[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in watermarks:
        count = _int_value(row.get("warning_count_delta"))
        if count < 1:
            continue
        source_type = str(row["source_type"])
        counts[source_type] = counts.get(source_type, 0) + count
    return counts


def _source_scan_counts(
    watermarks: Sequence[dict[str, object]],
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in watermarks:
        value = _int_value(row.get(field))
        if value < 1 and field != "elapsed_ms":
            continue
        source_type = str(row["source_type"])
        counts[source_type] = counts.get(source_type, 0) + value
    return counts


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _warning_event_counts(
    warnings: Sequence[dict[str, str]],
    source_warning_counts: Mapping[str, int],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for warning in warnings:
        event = warning["event"]
        if event == "connector.parse_warning":
            continue
        counts[event] = counts.get(event, 0) + 1
    parse_warning_count = sum(source_warning_counts.values())
    if parse_warning_count:
        counts["connector.parse_warning"] = parse_warning_count
    return counts


def _next_steps_for_status(report_status: str) -> list[str]:
    if report_status == "empty":
        return [
            "uv run python -m tradar.cli.app scan",
            "uv run python -m tradar.cli.app run --days 30",
        ]
    if report_status == "partial":
        return [
            "uv run python -m tradar.cli.app sources doctor",
            "uv run python -m tradar.cli.app run --days 30",
        ]
    if report_status == "low_confidence":
        return ["uv run python -m tradar.cli.app run --days 30 --agent codex"]
    return []


def _report_from_pack(
    config: RadarConfig,
    pack: EvidencePack,
    days: int,
    evidence_count: int,
    warning_count: int,
    run_id: str,
) -> RadarReport:
    generated_at = utc_now()
    return RadarReport(
        run_summary=RunSummary(
            run_id=run_id,
            generated_at=generated_at,
            timezone="Asia/Shanghai",
            days_window=days,
            config_path=str(config.config_path),
            evidence_count=evidence_count,
            warning_count=warning_count,
            rendered_by="base",
            confidence_note=(
                "Base report only summarizes evidence; use --agent codex for project judgment."
            ),
        ),
        opportunity_cards=[],
        this_weeks_demo=None,
        decision_prompt=DecisionPrompt(
            should_not_do=["不要把 base report 当成最终项目判断。"],
            needs_user_confirmation=["如需生成真实项目机会卡，使用 --agent codex。"],
        ),
    )


def _with_runtime_summary(
    report: RadarReport,
    config: RadarConfig,
    run_id: str,
    run_dir: Path,
    days: int,
    evidence_count: int,
    warning_count: int,
    agent_mode: str,
    render_mode: str,
    prompt_assets: PromptAssets | None,
    source_health: SourceHealth,
    raw_output: AgentRawOutput | None,
    repair_trace: _SchemaRepairTrace | None,
) -> RadarReport:
    config_overrides = dict(report.run_summary.config_overrides)
    config_overrides.update({"agent_mode": agent_mode, "render_mode": render_mode})
    if prompt_assets is not None:
        config_overrides.update(
            {
                "analyst_prompt_path": prompt_assets.analyst.path,
                "analyst_prompt_hash": prompt_assets.analyst.content_hash,
                "schema_repair_prompt_path": prompt_assets.schema_repair.path,
                "schema_repair_prompt_hash": prompt_assets.schema_repair.content_hash,
                "html_design_prompt_path": prompt_assets.html_design.path,
                "html_design_prompt_hash": prompt_assets.html_design.content_hash,
            }
        )
    run_summary = report.run_summary.copy(
        update={
            "run_id": run_id,
            "generated_at": utc_now(),
            "timezone": "Asia/Shanghai",
            "days_window": days,
            "config_path": str(config.config_path),
            "config_overrides": config_overrides,
            "evidence_count": evidence_count,
            "warning_count": warning_count,
            "rendered_by": "base",
            "debug_bundle_path": str(run_dir),
            "sources_requested": source_health.requested,
            "sources_succeeded": source_health.succeeded,
            "sources_failed": source_health.failed,
            "report_status": source_health.report_status,
            "next_steps": source_health.next_steps,
            "status_notes": source_health.status_notes,
            "warning_events": source_health.warning_events,
            "source_warning_counts": source_health.source_warning_counts,
            "source_scan_file_counts": source_health.source_scan_file_counts,
            "source_scan_elapsed_ms": source_health.source_scan_elapsed_ms,
            "search_used_count": sum(
                1 for card in report.opportunity_cards if card.search_trace.used_search
            ),
            "search_trace_summary": raw_output.search_trace_summary if raw_output else "",
            "agent_elapsed_ms": raw_output.elapsed_ms if raw_output else None,
            "repair_used": repair_trace.calls > 0 if repair_trace else False,
            "repair_elapsed_ms": (
                repair_trace.elapsed_ms if repair_trace and repair_trace.calls > 0 else None
            ),
            "confidence_note": report.run_summary.confidence_note or _default_confidence_note(
                agent_mode
            ),
        }
    )
    return report.copy(update={"run_summary": run_summary})


def _normalize_opportunity_cards(
    report: RadarReport,
    pack: EvidencePack,
    database_path: Path,
) -> RadarReport:
    if not report.opportunity_cards:
        return report

    evidence_by_id = {item.evidence_id: item for item in pack.items}
    decision_store = DecisionStateStore(database_path)
    decision_store.initialize()
    id_map: dict[str, str] = {}
    normalized_cards = []

    for card in report.opportunity_cards:
        original_id = card.card_id
        card_id = generate_card_id(card.title, card.evidence_ids)
        if original_id:
            id_map[original_id] = card_id
        normalized_cards.append(
            card.copy(
                update={
                    "card_id": card_id,
                    "status_hint": _status_hint_for_card(
                        card_id,
                        card.evidence_ids,
                        evidence_by_id,
                        decision_store,
                    ),
                }
            )
        )

    demo = report.this_weeks_demo
    normalized_demo = None
    if demo is not None:
        demo_card_id = id_map.get(demo.card_id, demo.card_id)
        normalized_demo = demo.copy(
            update={
                "card_id": demo_card_id,
                "start_command": f"tradar accept {demo_card_id}",
                "skip_command": f"tradar snooze {demo_card_id}",
            }
        )

    suggested_card_id = report.decision_prompt.suggested_start_card_id
    if suggested_card_id is not None:
        suggested_card_id = id_map.get(suggested_card_id, suggested_card_id)
    elif normalized_demo is not None:
        suggested_card_id = normalized_demo.card_id
    else:
        suggested_card_id = normalized_cards[0].card_id

    decision_prompt = report.decision_prompt.copy(
        update={
            "suggested_start_card_id": suggested_card_id,
            "start_command": f"tradar accept {suggested_card_id}",
            "snooze_command": f"tradar snooze {suggested_card_id}",
            "reject_command": f"tradar reject {suggested_card_id}",
        }
    )
    return report.copy(
        update={
            "opportunity_cards": normalized_cards,
            "this_weeks_demo": normalized_demo,
            "decision_prompt": decision_prompt,
        }
    )


def _status_hint_for_card(
    card_id: str,
    evidence_ids: list[str],
    evidence_by_id: Mapping[str, object],
    decision_store: DecisionStateStore,
) -> str:
    if decision_store.get(card_id) is not None:
        return "previously_seen"
    recurrence_total = 0
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        recurrence_total += int(getattr(evidence, "recurrence_count", 1))
    if recurrence_total > len(evidence_ids):
        return "recurring"
    return "new"


def _default_confidence_note(agent_mode: str) -> str:
    if agent_mode == "base":
        return "Base report only summarizes evidence; use --agent codex for project judgment."
    return "Analyst agent output was schema-validated against local evidence ids."


def _with_rendered_by(
    report: RadarReport,
    rendered_by: str,
    enhanced_elapsed_ms: int | None = None,
) -> RadarReport:
    run_summary = report.run_summary.copy(
        update={"rendered_by": rendered_by, "enhanced_elapsed_ms": enhanced_elapsed_ms}
    )
    return report.copy(update={"run_summary": run_summary})


class _SchemaRepairTrace(SchemaRepairAdapter):
    def __init__(self, adapter: SchemaRepairAdapter) -> None:
        self.adapter = adapter
        self.calls = 0
        self.elapsed_ms = 0

    def repair(self, raw_text: str, error_message: str) -> str:
        self.calls += 1
        started = perf_counter()
        try:
            return self.adapter.repair(raw_text, error_message)
        finally:
            self.elapsed_ms += _elapsed_ms(started)


def _load_prompt_assets() -> PromptAssets:
    return PromptAssets(
        analyst=load_prompt_asset("analyst", str(_PROMPT_DIR / "analyst.md")),
        schema_repair=load_prompt_asset(
            "schema_repair",
            str(_PROMPT_DIR / "schema_repair.md"),
        ),
        html_design=load_prompt_asset("html_design", str(_PROMPT_DIR / "html_design.md")),
    )


def _agent_adapter_for_mode(
    agent_mode: str,
    agent_adapter: AgentAdapter | None,
    config: RadarConfig,
) -> AgentAdapter:
    if agent_adapter is not None:
        return agent_adapter
    if agent_mode == "codex":
        return CodexAdapter(timeout_seconds=config.agent_timeout_seconds)
    raise ValueError("unknown agent mode: " + agent_mode)


def _schema_repair_adapter_for_mode(
    agent_mode: str,
    prompt_assets: PromptAssets,
    run_context: RunContext,
    config: RadarConfig,
) -> SchemaRepairAdapter | None:
    if agent_mode == "codex":
        return CodexSchemaRepairAdapter(
            prompt_asset=prompt_assets.schema_repair,
            output_dir=run_context.output_dir,
            timeout_seconds=config.schema_repair_timeout_seconds,
        )
    return None


def _html_enhancer_for_mode(
    render_mode: str,
    prompt_assets: PromptAssets | None,
    run_dir: Path,
    html_enhancer: Enhancer | None,
    config: RadarConfig,
) -> Enhancer | None:
    if render_mode == "base":
        return None
    if html_enhancer is not None:
        return html_enhancer
    assets = prompt_assets or _load_prompt_assets()
    return CodexHtmlEnhancer(
        prompt_asset=assets.html_design,
        output_dir=str(run_dir),
        timeout_seconds=config.html_design_timeout_seconds,
    )


def _render_warning_rows(warnings: list[str]) -> list[dict[str, str]]:
    return [
        {
            "event": warning,
            "level": "warn",
            "source_type": "renderer",
            "source_ref": "enhanced_html",
            "message": get_event_definition(warning).default_user_message,
        }
        for warning in warnings
    ]


def _with_warning_run_id(
    warnings: Sequence[Mapping[str, str]],
    run_id: str,
) -> list[dict[str, str]]:
    return [{"run_id": run_id, **dict(warning)} for warning in warnings]


def _render_log(render_result: RenderResult) -> str:
    parts = [f"rendered_by={render_result.rendered_by}"]
    if render_result.enhanced_elapsed_ms is not None:
        parts.append(f"enhanced_elapsed_ms={render_result.enhanced_elapsed_ms}")
    if render_result.warnings:
        parts.append("warnings=" + ",".join(render_result.warnings))
    return " ".join(parts)


def _require_agent_mode(agent_mode: str) -> str:
    if agent_mode not in {"base", "codex"}:
        raise CliUsageError("config.invalid_agent_mode", "use_--agent_base_or_codex")
    return agent_mode


def _require_render_mode(render_mode: str) -> str:
    if render_mode not in {"base", "enhanced"}:
        raise CliUsageError("config.invalid_render_mode", "use_--render_base_or_enhanced")
    return render_mode


def _agent_raw_artifact(
    raw_output: AgentRawOutput,
    prompt_assets: PromptAssets,
    agent_mode: str,
) -> dict[str, object]:
    return {
        "mode": agent_mode,
        "raw_text": raw_output.raw_text,
        "elapsed_ms": raw_output.elapsed_ms,
        "search_trace_summary": raw_output.search_trace_summary,
        "warnings": raw_output.warnings,
        "prompt_assets": {
            "analyst": _prompt_asset_artifact(
                prompt_assets.analyst.path,
                prompt_assets.analyst.content_hash,
            ),
            "schema_repair": _prompt_asset_artifact(
                prompt_assets.schema_repair.path,
                prompt_assets.schema_repair.content_hash,
            ),
            "html_design": _prompt_asset_artifact(
                prompt_assets.html_design.path,
                prompt_assets.html_design.content_hash,
            ),
        },
    }


def _prompt_asset_artifact(path: str, content_hash: str) -> dict[str, str]:
    return {"path": path, "content_hash": content_hash}


def _validate_report_evidence_ids(report: RadarReport, pack: EvidencePack) -> None:
    known_ids = {item.evidence_id for item in pack.items}
    referenced_ids: set[str] = set()
    for card in report.opportunity_cards:
        referenced_ids.update(card.evidence_ids)
    unknown_ids = sorted(referenced_ids - known_ids)
    if unknown_ids:
        raise AgentOutputSchemaError(
            "agent referenced unknown evidence ids: " + ", ".join(unknown_ids)
        )


def _new_run_id() -> str:
    return "run_" + utc_now().strftime("%Y%m%d%H%M%S%f")


def _save_decision(card_id: str, decision: str) -> None:
    config = load_config(_config_path())
    known_card_ids = _known_card_ids_from_reports(config.output_dir)
    if card_id not in known_card_ids:
        definition = get_event_definition("decision.unknown_card_id")
        typer.echo(
            f"{definition.severity} {definition.event} "
            f"{definition.default_user_message} card_id={card_id} "
            "next_action=run_radar_generate_or_use_report_card_id"
        )
        raise typer.Exit(1)

    store = DecisionStateStore(config.database_path)
    store.initialize()
    state = store.save(DecisionState(card_id=card_id, decision=decision))
    typer.echo(f"decision_saved={state.card_id} {state.decision}")


def _known_card_ids_from_reports(output_dir: Path) -> set[str]:
    known_card_ids: set[str] = set()
    if not output_dir.exists():
        return known_card_ids

    for report_path in sorted(output_dir.glob("*/validated_report.json"), reverse=True):
        try:
            report = RadarReport.parse_raw(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        known_card_ids.update(card.card_id for card in report.opportunity_cards if card.card_id)
        if report.this_weeks_demo is not None:
            known_card_ids.add(report.this_weeks_demo.card_id)
    return known_card_ids


def _print_cli_usage_error(error: CliUsageError) -> None:
    definition = get_event_definition(error.event)
    typer.echo(
        f"{definition.severity} {definition.event} "
        f"{definition.default_user_message} next_action={error.next_action}"
    )


def _print_agent_execution_error(error: AgentAdapterExecutionError) -> None:
    definition = get_event_definition(error.event)
    artifact = f" artifact_path={error.artifact_path}" if error.artifact_path else ""
    typer.echo(
        f"{definition.severity} {definition.event} "
        f"{definition.default_user_message}{artifact} "
        "next_action=inspect_agent_prompt_and_retry"
    )
    typer.echo(str(error))


def _print_agent_schema_error(error: AgentOutputSchemaError) -> None:
    definition = get_event_definition("agent.schema_invalid")
    run_id = f" run_id={error.run_id}" if error.run_id else ""
    artifact = f" artifact_path={error.artifact_path}" if error.artifact_path else ""
    typer.echo(
        f"{definition.severity} {definition.event} "
        f"{definition.default_user_message}{run_id}{artifact} "
        "next_action=inspect_agent_raw_output_and_schema_repair"
    )
    typer.echo(str(error))


def _print_doctor_issues(issues: Iterable[DoctorIssue]) -> None:
    printed = False
    for issue in issues:
        printed = True
        suffix = f" path={issue.path}" if issue.path else ""
        typer.echo(f"{issue.severity} {issue.event} {issue.message}{suffix}")
    if not printed:
        typer.echo("doctor_ok=true")


def _config_path() -> Path:
    return _CLI_STATE["config_path"]


def _privacy_gate_from_context(ctx: typer.Context) -> PrivacyGateProtocol:
    obj = ctx.obj
    if isinstance(obj, dict):
        gate = obj.get("privacy_gate")
        if gate is not None:
            return cast(PrivacyGateProtocol, gate)
    return PrivacyGate()


def _is_broad_root(path: Path) -> bool:
    resolved = Path(path).expanduser()
    broad = {Path("/"), Path.home(), Path("/Users"), Path("/System"), Path("/Library")}
    return resolved in broad


def _repo_root_containing(path: Path) -> Path | None:
    resolved = Path(path).expanduser().resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _output_dir_unwritable(path: Path) -> bool:
    output_dir = Path(path).expanduser()
    if output_dir.exists() and not output_dir.is_dir():
        return True
    parent = output_dir if output_dir.exists() else _nearest_existing_parent(output_dir)
    return not os.access(parent, os.W_OK)


def _nearest_existing_parent(path: Path) -> Path:
    for candidate in path.parents:
        if candidate.exists():
            return candidate
    return Path("/")


if __name__ == "__main__":
    app()
