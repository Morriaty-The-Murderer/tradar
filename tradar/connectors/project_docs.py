"""项目文档 connector。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tradar.schemas import RawEvent


def parse_project_doc(path: Path, root: Path | None = None) -> RawEvent:
    doc_path = Path(path)
    text = doc_path.read_text(encoding="utf-8")
    base = Path(root) if root is not None else doc_path.parent
    source_id = doc_path.relative_to(base).as_posix()
    captured_at = datetime.fromtimestamp(doc_path.stat().st_mtime, UTC)
    title = _extract_markdown_title(text) or doc_path.stem

    return RawEvent(
        source_type="project_docs",
        source_id=source_id,
        source_path=str(doc_path),
        captured_at=captured_at,
        event_time=captured_at,
        title=title,
        raw_text=text,
        metadata={"root": str(base)},
    )


def _extract_markdown_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""
