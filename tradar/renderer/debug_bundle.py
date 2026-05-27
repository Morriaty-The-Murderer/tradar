"""Debug bundle artifact writer。"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel


def write_debug_bundle(
    run_dir: Path,
    run_record: BaseModel,
    warnings: Iterable[Any],
    evidence_pack: Any,
    agent_raw_output: Any,
    validated_report: BaseModel,
    render_log: str,
    report_html: str,
    save_agent_raw_output: bool = True,
) -> None:
    output_dir = Path(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_record = _with_validated_run_summary(run_record, validated_report)

    _write_json(output_dir / "run.json", run_record)
    _write_jsonl(output_dir / "warnings.jsonl", warnings)
    _write_json(output_dir / "evidence_pack.json", evidence_pack)
    if save_agent_raw_output:
        _write_json(output_dir / "agent_raw_output.json", agent_raw_output)
    _write_json(output_dir / "validated_report.json", validated_report)
    (output_dir / "render.log").write_text(render_log, encoding="utf-8")
    (output_dir / "report.html").write_text(report_html, encoding="utf-8")


def _with_validated_run_summary(run_record: BaseModel, validated_report: BaseModel) -> BaseModel:
    if "run_summary" not in getattr(run_record, "__fields__", {}):
        return run_record
    if getattr(run_record, "run_summary", None) is not None:
        return run_record
    report_summary = getattr(validated_report, "run_summary", None)
    if report_summary is None:
        return run_record
    return run_record.copy(update={"run_summary": report_summary})


def apply_debug_retention(output_dir: Path, retain_count: int) -> list[str]:
    if retain_count < 1:
        return []
    root = Path(output_dir)
    if not root.exists():
        return []

    run_dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith("run_") and (path / "run.json").exists()
    ]
    ordered = sorted(run_dirs, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    deleted: list[str] = []
    for path in ordered[retain_count:]:
        shutil.rmtree(path)
        deleted.append(str(path))
    return deleted


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_to_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    lines = [json.dumps(_to_jsonable(row), ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return json.loads(value.json())
    if is_dataclass(value):
        return _to_jsonable(asdict(cast(Any, value)))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value
