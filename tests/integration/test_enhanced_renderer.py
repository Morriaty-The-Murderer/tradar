from __future__ import annotations

from tradar.renderer.enhanced import EnhancedRenderResult, render_with_optional_enhancement
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
