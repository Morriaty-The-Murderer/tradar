"""Claude Code session JSONL connector。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tradar.connectors.base import ConnectorCapabilities
from tradar.schemas import RawEvent
from tradar.schemas.time import ensure_utc_datetime


class ClaudeCodeSessionConnector:
    @staticmethod
    def describe_capabilities() -> ConnectorCapabilities:
        return ConnectorCapabilities(
            title="partial",
            timestamp="partial",
            role="supported",
            tool_calls="supported",
            files="partial",
            raw_text="supported",
        )


def parse_claude_code_session(path: Path) -> RawEvent:
    records = list(_read_jsonl(path))
    session_id = path.stem
    title: str | None = None
    timestamps: list[datetime] = []
    raw_parts: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    tool_call_count = 0

    for record in records:
        if record.get("sessionId"):
            session_id = str(record["sessionId"])

        timestamp = record.get("timestamp")
        if timestamp:
            timestamps.append(ensure_utc_datetime(timestamp))
        else:
            _append_warning(warnings, "record missing timestamp")

        if record.get("type") == "ai-title" and record.get("aiTitle"):
            title = str(record["aiTitle"])

        _capture_metadata(metadata, record)

        message = record.get("message")
        if isinstance(message, dict):
            text, tool_count = _extract_message_content(message.get("content"))
            tool_call_count += tool_count
            if text:
                raw_parts.append(text)

        if record.get("toolUseResult") is not None:
            tool_call_count += 1
            tool_text = _extract_tool_result(record.get("toolUseResult"))
            if tool_text:
                raw_parts.append(tool_text)

    captured_at = timestamps[0] if timestamps else _file_mtime(path)
    metadata["tool_call_count"] = tool_call_count
    metadata = {key: value for key, value in metadata.items() if value is not None}

    raw_text = "\n".join(raw_parts).strip()
    derived_title = title or _first_line(raw_text) or session_id

    return RawEvent(
        source_type="claude_code_session",
        source_id=session_id,
        source_path=str(path),
        captured_at=captured_at,
        event_time=captured_at,
        actor="session",
        title=derived_title,
        raw_text=raw_text or derived_title,
        metadata=metadata,
        parse_warnings=warnings,
    )


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            yield json.loads(stripped)


def _capture_metadata(metadata: dict[str, Any], record: dict[str, Any]) -> None:
    mapping = {
        "cwd": "cwd",
        "git_branch": "gitBranch",
        "entrypoint": "entrypoint",
        "version": "version",
    }
    for target, source in mapping.items():
        if target not in metadata and record.get(source):
            metadata[target] = record[source]


def _extract_message_content(content: Any) -> tuple[str, int]:
    if isinstance(content, str):
        return content.strip(), 0
    if not isinstance(content, list):
        return "", 0

    parts: list[str] = []
    tool_count = 0
    for block in content:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type == "text" and block.get("text"):
                parts.append(str(block["text"]))
            elif block_type == "tool_use":
                tool_count += 1
                parts.append("[tool_use] " + str(block.get("name") or "unknown_tool"))
            elif block_type == "tool_result":
                text = block.get("content")
                if text:
                    parts.append(str(text))
            elif block.get("text"):
                parts.append(str(block["text"]))
        elif block is not None:
            parts.append(str(block))
    return "\n".join(part.strip() for part in parts if part and part.strip()), tool_count


def _extract_tool_result(tool_result: Any) -> str:
    if isinstance(tool_result, str):
        return tool_result.strip()
    if isinstance(tool_result, dict):
        for key in ("content", "text"):
            if tool_result.get(key):
                return str(tool_result[key]).strip()
    return ""


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(Path(path).stat().st_mtime, UTC)


def _first_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)
