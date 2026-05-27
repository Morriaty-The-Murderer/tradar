"""Base HTML Renderer。"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tradar.schemas import RadarReport

REQUIRED_SECTIONS = [
    "Run Summary",
    "This Week's Demo",
    "Project Opportunity Cards",
    "Demo Briefs",
    "Decision Prompt",
]


def render_base_report(report: RadarReport) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    return template.render(report=report)


def validate_required_sections(html: str) -> list[str]:
    return [section for section in REQUIRED_SECTIONS if section not in html]
