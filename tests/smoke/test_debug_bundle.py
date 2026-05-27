from __future__ import annotations

import json
import os

from tradar.evidence.pack_builder import EvidencePack, OmittedSummary
from tradar.renderer.debug_bundle import apply_debug_retention, write_debug_bundle
from tradar.schemas import DecisionPrompt, RadarReport, RunRecord, RunSummary


def test_debug_bundle_writes_required_run_artifacts(tmp_path) -> None:
    report = RadarReport(
        run_summary=RunSummary(
            run_id="run_empty",
            generated_at="2026-05-24T08:00:00Z",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=0,
            warning_count=1,
            rendered_by="base",
        ),
        opportunity_cards=[],
        this_weeks_demo=None,
        decision_prompt=DecisionPrompt(
            should_not_do=["Do not start a demo without evidence."],
            needs_user_confirmation=["Run tradar sources doctor."],
        ),
    )
    pack = EvidencePack(items=[], omitted_summary=OmittedSummary(total_omitted=0))

    write_debug_bundle(
        run_dir=tmp_path,
        run_record=RunRecord(run_id="run_empty", status="empty"),
        warnings=[{"event": "report.empty", "level": "warn", "message": "No evidence."}],
        evidence_pack=pack,
        agent_raw_output={"status": "mocked"},
        validated_report=report,
        render_log="rendered_by=base",
        report_html="<html>empty</html>",
    )

    expected = {
        "run.json",
        "warnings.jsonl",
        "evidence_pack.json",
        "agent_raw_output.json",
        "validated_report.json",
        "render.log",
        "report.html",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected
    run_record = json.loads((tmp_path / "run.json").read_text())
    assert run_record["run_id"] == "run_empty"
    assert run_record["run_summary"]["run_id"] == "run_empty"
    assert run_record["run_summary"]["report_status"] == "complete"
    validated = json.loads((tmp_path / "validated_report.json").read_text())
    assert validated["run_summary"]["run_id"] == "run_empty"
    assert (tmp_path / "warnings.jsonl").read_text().strip().endswith("No evidence.\"}")


def test_debug_bundle_can_skip_agent_raw_output(tmp_path) -> None:
    report = RadarReport(
        run_summary=RunSummary(
            run_id="run_no_raw",
            generated_at="2026-05-24T08:00:00Z",
            timezone="Asia/Shanghai",
            days_window=30,
            evidence_count=0,
            warning_count=1,
            rendered_by="base",
        ),
        opportunity_cards=[],
        this_weeks_demo=None,
        decision_prompt=DecisionPrompt(
            should_not_do=["Do not start a demo without evidence."],
            needs_user_confirmation=["Run tradar sources doctor."],
        ),
    )

    write_debug_bundle(
        run_dir=tmp_path,
        run_record=RunRecord(run_id="run_no_raw", status="generated"),
        warnings=[{"event": "report.empty", "level": "warn", "message": "No evidence."}],
        evidence_pack=EvidencePack(items=[], omitted_summary=OmittedSummary(total_omitted=0)),
        agent_raw_output={"raw_text": "sensitive local evidence"},
        validated_report=report,
        render_log="rendered_by=base",
        report_html="<html>empty</html>",
        save_agent_raw_output=False,
    )

    assert not (tmp_path / "agent_raw_output.json").exists()
    assert (tmp_path / "validated_report.json").exists()
    assert (tmp_path / "warnings.jsonl").exists()


def test_debug_retention_deletes_only_old_run_dirs_with_run_record(tmp_path) -> None:
    output_dir = tmp_path / "runs"
    output_dir.mkdir()
    for index in range(4):
        run_dir = output_dir / f"run_20260524080{index}"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps({"run_id": run_dir.name}), encoding="utf-8")
        os.utime(run_dir, (index, index))
    non_run_dir = output_dir / "notes"
    non_run_dir.mkdir()
    (non_run_dir / "draft.txt").write_text("keep", encoding="utf-8")

    deleted = apply_debug_retention(output_dir, retain_count=2)

    assert deleted == [
        str(output_dir / "run_202605240801"),
        str(output_dir / "run_202605240800"),
    ]
    assert not (output_dir / "run_202605240800").exists()
    assert not (output_dir / "run_202605240801").exists()
    assert (output_dir / "run_202605240802").exists()
    assert (output_dir / "run_202605240803").exists()
    assert non_run_dir.exists()
