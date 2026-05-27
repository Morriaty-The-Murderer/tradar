"""Codex session JSONL connector。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tradar.connectors.base import ConnectorCapabilities
from tradar.schemas import RawEvent
from tradar.schemas.time import ensure_utc_datetime


class CodexSessionConnector:
    @staticmethod
    def describe_capabilities() -> ConnectorCapabilities:
        return ConnectorCapabilities(
            title="unsupported",
            timestamp="supported",
            role="partial",
            tool_calls="partial",
            files="partial",
            raw_text="partial",
        )


def parse_codex_session(path: Path) -> RawEvent:
    records = list(_read_jsonl(path))
    metadata: dict[str, Any] = {}
    session_id = path.stem
    timestamps: list[datetime] = []
    raw_parts: list[str] = []
    warnings: list[str] = []
    first_user_text: str | None = None
    first_summary: str | None = None
    tool_call_count = 0

    for record in records:
        timestamp = record.get("timestamp")
        if timestamp:
            timestamps.append(ensure_utc_datetime(timestamp))

        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue

        if record.get("type") == "session_meta":
            session_id = str(payload.get("id") or session_id)
            metadata.update(
                {
                    "cwd": payload.get("cwd"),
                    "cli_version": payload.get("cli_version"),
                    "model_provider": payload.get("model_provider"),
                    "thread_source": payload.get("thread_source"),
                }
            )
            continue

        if record.get("type") != "response_item":
            continue

        if payload.get("encrypted_content"):
            _append_warning(warnings, "response item contains encrypted_content")
            if payload.get("summary") and not first_summary:
                first_summary = str(payload["summary"])
            continue

        payload_type = str(payload.get("type") or "")
        if payload_type == "function_call" or payload.get("name"):
            tool_call_count += 1
            name = str(payload.get("name") or "unknown_tool")
            arguments = str(payload.get("arguments") or "")
            raw_parts.append("[tool_call] " + name + " " + arguments)
            continue

        if payload_type == "function_call_output":
            output = str(payload.get("output") or "")
            if output:
                raw_parts.append("[tool_output] " + output)
            continue

        text = _extract_content_text(payload.get("content"))
        if text:
            role = payload.get("role")
            if role == "user" and first_user_text is None:
                first_user_text = text
            raw_parts.append(text)

    captured_at = timestamps[0] if timestamps else _file_mtime(path)
    title = first_user_text or first_summary or session_id
    metadata["tool_call_count"] = tool_call_count
    metadata = {key: value for key, value in metadata.items() if value is not None}

    return RawEvent(
        source_type="codex_session",
        source_id=session_id,
        source_path=str(path),
        captured_at=captured_at,
        event_time=captured_at,
        actor="session",
        title=title,
        raw_text="\n".join(raw_parts).strip() or title,
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


def _extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            text = block.get("text") or block.get("content")
            if text:
                parts.append(str(text))
        elif block is not None:
            parts.append(str(block))
    return " ".join(part.strip() for part in parts if part and part.strip())


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(Path(path).stat().st_mtime, UTC)


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)
