from __future__ import annotations

from datetime import UTC
from pathlib import Path

from tradar.connectors.claude_code import (
    ClaudeCodeSessionConnector,
    parse_claude_code_session,
)
from tradar.connectors.codex import CodexSessionConnector, parse_codex_session
from tradar.connectors.git_commits import parse_git_commit_line
from tradar.connectors.project_docs import parse_project_doc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_connector_capabilities_match_source_discovery() -> None:
    codex = CodexSessionConnector.describe_capabilities()
    claude = ClaudeCodeSessionConnector.describe_capabilities()

    assert codex.title == "unsupported"
    assert codex.timestamp == "supported"
    assert codex.role == "partial"
    assert codex.tool_calls == "partial"
    assert codex.files == "partial"
    assert codex.raw_text == "partial"

    assert claude.title == "partial"
    assert claude.timestamp == "partial"
    assert claude.role == "supported"
    assert claude.tool_calls == "supported"
    assert claude.files == "partial"
    assert claude.raw_text == "supported"


def test_codex_session_fixture_parses_to_raw_event() -> None:
    event = parse_codex_session(FIXTURES / "codex" / "happy_path.jsonl")

    assert event.source_type == "codex_session"
    assert event.source_id == "codex-session-1"
    assert event.captured_at.tzinfo == UTC
    assert event.event_time == event.captured_at
    assert event.title == "Build Tradar from local agent sessions."
    assert "exec_command" in event.raw_text
    assert event.metadata["cwd"] == "<USER_HOME>/PycharmProjects/<REPO_NAME>"
    assert event.metadata["tool_call_count"] == 1
    assert event.parse_warnings == []


def test_codex_session_records_encrypted_content_warning() -> None:
    event = parse_codex_session(FIXTURES / "codex" / "encrypted_content.jsonl")

    assert event.source_id == "codex-session-encrypted"
    assert event.title == "User asked for a private local analysis."
    assert "encrypted_content" not in event.raw_text
    assert "response item contains encrypted_content" in event.parse_warnings


def test_codex_noisy_proactive_fixture_parses_sanitized_public_example() -> None:
    event = parse_codex_session(FIXTURES / "codex" / "noisy_proactive_loop.jsonl")

    assert event.source_id == "codex-session-proactive"
    assert event.metadata["cwd"] == "<USER_HOME>/PycharmProjects/<REPO_NAME>"
    assert event.metadata["tool_call_count"] == 1
    assert "proactive signal loop" in event.raw_text
    assert "/Users/" not in event.raw_text
    assert "sk-" not in event.raw_text


def test_claude_code_fixture_parses_to_raw_event() -> None:
    event = parse_claude_code_session(FIXTURES / "claude" / "happy_path.jsonl")

    assert event.source_type == "claude_code_session"
    assert event.source_id == "claude-session-1"
    assert event.title == "Quick Match QA Checklist"
    assert event.metadata["cwd"] == "<USER_HOME>/GolandProjects/src/<REPO_NAME>"
    assert event.metadata["git_branch"] == "main"
    assert event.metadata["tool_call_count"] == 2
    assert "black-box language" in event.raw_text
    assert "soft ranking weights" in event.raw_text


def test_claude_skill_trace_fixture_parses_sanitized_public_example() -> None:
    event = parse_claude_code_session(FIXTURES / "claude" / "skill_trace.jsonl")

    assert event.source_id == "claude-session-skill-trace"
    assert event.title == "Tradar Skill Loop"
    assert event.metadata["cwd"] == "<USER_HOME>/PycharmProjects/<REPO_NAME>"
    assert event.metadata["tool_call_count"] == 2
    assert "tradar run --days 30" in event.raw_text
    assert "/Users/" not in event.raw_text
    assert "sk-" not in event.raw_text


def test_claude_code_missing_timestamp_falls_back_to_file_mtime() -> None:
    event = parse_claude_code_session(FIXTURES / "claude" / "missing_timestamp.jsonl")

    assert event.source_id == "claude-session-missing-ts"
    assert event.captured_at.tzinfo == UTC
    assert "record missing timestamp" in event.parse_warnings
    assert event.raw_text == "Summarize this project."


def test_project_doc_uses_h1_as_title_and_file_path_as_source_id() -> None:
    path = FIXTURES / "project_docs" / "basic_doc.md"
    event = parse_project_doc(path, root=FIXTURES)

    assert event.source_type == "project_docs"
    assert event.source_id == "project_docs/basic_doc.md"
    assert event.title == "Basic Project Document"
    assert "local agent-native workflow" in event.raw_text


def test_project_doc_fixture_covers_sanitized_docs_and_notes() -> None:
    docs_event = parse_project_doc(
        FIXTURES / "project_docs" / "docs" / "release_checklist.md",
        root=FIXTURES / "project_docs",
    )
    notes_event = parse_project_doc(
        FIXTURES / "project_docs" / "notes" / "first_user_decision.md",
        root=FIXTURES / "project_docs",
    )

    assert docs_event.source_id == "docs/release_checklist.md"
    assert docs_event.title == "Release Checklist"
    assert "sanitized fixture" in docs_event.raw_text
    assert notes_event.source_id == "notes/first_user_decision.md"
    assert notes_event.title == "First User Decision"
    assert "private path" not in notes_event.raw_text


def test_git_commit_line_parses_subject_and_date() -> None:
    event = parse_git_commit_line(
        "abc1234\t2026-05-22\tfeat(algo): add recommendation reason templates",
        repo_path="/repo",
    )

    assert event.source_type == "git_commit"
    assert event.source_id == "abc1234"
    assert event.title == "feat(algo): add recommendation reason templates"
    assert event.captured_at.tzinfo == UTC
    assert event.metadata["repo_path"] == "/repo"
