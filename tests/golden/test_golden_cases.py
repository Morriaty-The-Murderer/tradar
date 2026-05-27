from __future__ import annotations

import json
from pathlib import Path

import pytest

from tradar.golden.checklist import evaluate_golden_report, load_evidence_pack
from tradar.schemas import RadarReport

pytestmark = pytest.mark.llm_eval

CASES_DIR = Path(__file__).parent / "cases"


def test_golden_cases_match_expected_checklist() -> None:
    case_dirs = sorted(path for path in CASES_DIR.iterdir() if path.is_dir())
    assert case_dirs

    for case_dir in case_dirs:
        report = RadarReport.parse_raw(
            (case_dir / "validated_report.json").read_text(encoding="utf-8")
        )
        pack = load_evidence_pack(case_dir / "evidence_pack.json")
        expected = json.loads((case_dir / "expected_checklist.json").read_text(encoding="utf-8"))

        result = evaluate_golden_report(report, pack)

        assert result.failures == expected["failures"], case_dir.name
        assert sorted(result.manual_checks) == sorted(expected["manual_checks"]), case_dir.name
