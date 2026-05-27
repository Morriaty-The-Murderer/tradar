"""Git commit subject connector。"""

from __future__ import annotations

from datetime import UTC, datetime

from tradar.schemas import RawEvent


def parse_git_commit_line(line: str, repo_path: str) -> RawEvent:
    parts = line.rstrip("\n").split("\t", 2)
    if len(parts) != 3:
        raise ValueError("git commit line must be '<hash>\\t<YYYY-MM-DD>\\t<subject>'")

    commit_hash, date_text, subject = parts
    captured_at = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC)

    return RawEvent(
        source_type="git_commit",
        source_id=commit_hash,
        source_path=repo_path,
        captured_at=captured_at,
        event_time=captured_at,
        actor="git",
        title=subject,
        raw_text=line.rstrip("\n"),
        metadata={"repo_path": repo_path, "commit_hash": commit_hash},
    )
