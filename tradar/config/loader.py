"""用户级 TOML 配置加载。"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tradar.config.defaults import (
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    DEFAULT_CLAUDE_BINARY,
    DEFAULT_CLAUDE_PROJECT_PATH,
    DEFAULT_CODEX_BINARY,
    DEFAULT_CODEX_SESSION_PATH,
    DEFAULT_DAYS_WINDOW,
    DEFAULT_DEBUG_RETENTION_RUN_COUNT,
    DEFAULT_HTML_DESIGN_TIMEOUT_SECONDS,
    DEFAULT_LOW_CONFIDENCE_EVIDENCE_THRESHOLD,
    DEFAULT_MAX_PACK_TOKENS,
    DEFAULT_MAX_SOURCE_FILE_BYTES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SCHEMA_REPAIR_TIMEOUT_SECONDS,
    DEFAULT_STATE_DIR,
)


@dataclass(frozen=True)
class RadarConfig:
    config_path: Path
    codex_session_paths: list[Path]
    claude_project_paths: list[Path]
    project_roots: list[Path]
    output_dir: Path
    state_dir: Path
    days_window: int = DEFAULT_DAYS_WINDOW
    allow_broad_root: bool = False
    max_evidence_items: int = 120
    max_pack_tokens: int = DEFAULT_MAX_PACK_TOKENS
    max_source_file_bytes: int = DEFAULT_MAX_SOURCE_FILE_BYTES
    agent_timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
    schema_repair_timeout_seconds: int = DEFAULT_SCHEMA_REPAIR_TIMEOUT_SECONDS
    html_design_timeout_seconds: int = DEFAULT_HTML_DESIGN_TIMEOUT_SECONDS
    codex_binary: str = DEFAULT_CODEX_BINARY
    claude_binary: str = DEFAULT_CLAUDE_BINARY
    save_agent_raw_output: bool = True
    debug_retention_run_count: int = DEFAULT_DEBUG_RETENTION_RUN_COUNT
    low_confidence_evidence_threshold: int = DEFAULT_LOW_CONFIDENCE_EVIDENCE_THRESHOLD

    @property
    def database_path(self) -> Path:
        return self.state_dir / "tradar.sqlite"


def load_config(config_path: Path) -> RadarConfig:
    path = Path(config_path).expanduser()
    if not path.exists():
        raise FileNotFoundError("config file not found: " + str(path))

    data = _parse_toml_subset(path.read_text(encoding="utf-8"))
    return RadarConfig(
        config_path=path,
        codex_session_paths=_paths(data.get("codex_session_paths", [])),
        claude_project_paths=_paths(data.get("claude_project_paths", [])),
        project_roots=_paths(data.get("project_roots", [])),
        output_dir=Path(data.get("output_dir") or DEFAULT_OUTPUT_DIR).expanduser(),
        state_dir=Path(data.get("state_dir") or DEFAULT_STATE_DIR).expanduser(),
        days_window=int(data.get("days_window") or DEFAULT_DAYS_WINDOW),
        allow_broad_root=bool(data.get("allow_broad_root", False)),
        max_evidence_items=int(data.get("max_evidence_items") or 120),
        max_pack_tokens=_int_with_default(data, "max_pack_tokens", DEFAULT_MAX_PACK_TOKENS),
        max_source_file_bytes=_int_with_default(
            data,
            "max_source_file_bytes",
            DEFAULT_MAX_SOURCE_FILE_BYTES,
        ),
        agent_timeout_seconds=_int_with_default(
            data,
            "agent_timeout_seconds",
            DEFAULT_AGENT_TIMEOUT_SECONDS,
        ),
        schema_repair_timeout_seconds=_int_with_default(
            data,
            "schema_repair_timeout_seconds",
            DEFAULT_SCHEMA_REPAIR_TIMEOUT_SECONDS,
        ),
        html_design_timeout_seconds=_int_with_default(
            data,
            "html_design_timeout_seconds",
            DEFAULT_HTML_DESIGN_TIMEOUT_SECONDS,
        ),
        codex_binary=str(data.get("codex_binary") or DEFAULT_CODEX_BINARY),
        claude_binary=str(data.get("claude_binary") or DEFAULT_CLAUDE_BINARY),
        save_agent_raw_output=bool(data.get("save_agent_raw_output", True)),
        debug_retention_run_count=_int_with_default(
            data,
            "debug_retention_run_count",
            DEFAULT_DEBUG_RETENTION_RUN_COUNT,
        ),
        low_confidence_evidence_threshold=_int_with_default(
            data,
            "low_confidence_evidence_threshold",
            DEFAULT_LOW_CONFIDENCE_EVIDENCE_THRESHOLD,
        ),
    )


def write_default_config(
    config_path: Path,
    codex_session_paths: list[Path] | None = None,
    claude_project_paths: list[Path] | None = None,
    project_roots: list[Path] | None = None,
    output_dir: Path | None = None,
    state_dir: Path | None = None,
) -> Path:
    path = Path(config_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _array_line(
            "codex_session_paths",
            [DEFAULT_CODEX_SESSION_PATH] if codex_session_paths is None else codex_session_paths,
        ),
        _array_line(
            "claude_project_paths",
            [DEFAULT_CLAUDE_PROJECT_PATH] if claude_project_paths is None else claude_project_paths,
        ),
        _array_line("project_roots", project_roots or []),
        f'output_dir = "{output_dir or DEFAULT_OUTPUT_DIR}"',
        f'state_dir = "{state_dir or DEFAULT_STATE_DIR}"',
        f"days_window = {DEFAULT_DAYS_WINDOW}",
        "allow_broad_root = false",
        "max_evidence_items = 120",
        f"max_pack_tokens = {DEFAULT_MAX_PACK_TOKENS}",
        f"max_source_file_bytes = {DEFAULT_MAX_SOURCE_FILE_BYTES}",
        f"agent_timeout_seconds = {DEFAULT_AGENT_TIMEOUT_SECONDS}",
        f"schema_repair_timeout_seconds = {DEFAULT_SCHEMA_REPAIR_TIMEOUT_SECONDS}",
        f"html_design_timeout_seconds = {DEFAULT_HTML_DESIGN_TIMEOUT_SECONDS}",
        f'codex_binary = "{DEFAULT_CODEX_BINARY}"',
        f'claude_binary = "{DEFAULT_CLAUDE_BINARY}"',
        "save_agent_raw_output = true",
        f"debug_retention_run_count = {DEFAULT_DEBUG_RETENTION_RUN_COUNT}",
        f"low_confidence_evidence_threshold = {DEFAULT_LOW_CONFIDENCE_EVIDENCE_THRESHOLD}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _parse_toml_subset(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() == "true":
            result[key] = True
        elif value.lower() == "false":
            result[key] = False
        else:
            try:
                result[key] = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                result[key] = value.strip('"').strip("'")
    return result


def _paths(values: Any) -> list[Path]:
    if values is None:
        return []
    if isinstance(values, (str, Path)):
        values = [values]
    return [Path(str(value)).expanduser() for value in values]


def _int_with_default(data: dict[str, Any], key: str, default: int) -> int:
    if key not in data:
        return default
    return int(data[key])


def _array_line(name: str, values: list[Path]) -> str:
    rendered = ", ".join(f'"{value}"' for value in values)
    return f"{name} = [{rendered}]"
