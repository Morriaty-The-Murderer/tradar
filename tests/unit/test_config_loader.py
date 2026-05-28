from __future__ import annotations

from pathlib import Path

from tradar.config.loader import load_config, write_default_config


def test_config_loads_save_agent_raw_output_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "codex_session_paths = []",
                "claude_project_paths = []",
                "project_roots = []",
                'output_dir = "{}"'.format(tmp_path / "runs"),
                'state_dir = "{}"'.format(tmp_path / "state"),
                "save_agent_raw_output = false",
                "max_pack_tokens = 1234",
                "max_source_file_bytes = 12",
                "agent_timeout_seconds = 11",
                "schema_repair_timeout_seconds = 12",
                "html_design_timeout_seconds = 13",
                'codex_binary = "/opt/bin/codex-preview"',
                'claude_binary = "/opt/bin/claude-code"',
                "debug_retention_run_count = 7",
                "low_confidence_evidence_threshold = 9",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.save_agent_raw_output is False
    assert config.max_pack_tokens == 1234
    assert config.max_source_file_bytes == 12
    assert config.agent_timeout_seconds == 11
    assert config.schema_repair_timeout_seconds == 12
    assert config.html_design_timeout_seconds == 13
    assert config.codex_binary == "/opt/bin/codex-preview"
    assert config.claude_binary == "/opt/bin/claude-code"
    assert config.debug_retention_run_count == 7
    assert config.low_confidence_evidence_threshold == 9


def test_default_config_keeps_agent_raw_output_enabled(tmp_path: Path) -> None:
    config_path = write_default_config(tmp_path / "config.toml")

    config = load_config(config_path)

    assert config.save_agent_raw_output is True
    assert config.max_pack_tokens == 24000
    assert config.max_source_file_bytes == 5 * 1024 * 1024
    assert config.agent_timeout_seconds == 300
    assert config.schema_repair_timeout_seconds == 300
    assert config.html_design_timeout_seconds == 300
    assert config.codex_binary == "codex"
    assert config.claude_binary == "claude"
    assert config.debug_retention_run_count == 20
    assert config.low_confidence_evidence_threshold == 3
    assert "save_agent_raw_output = true" in config_path.read_text(encoding="utf-8")
    assert "max_pack_tokens = 24000" in config_path.read_text(encoding="utf-8")
    assert "max_source_file_bytes = 5242880" in config_path.read_text(encoding="utf-8")
    assert "agent_timeout_seconds = 300" in config_path.read_text(encoding="utf-8")
    assert "schema_repair_timeout_seconds = 300" in config_path.read_text(encoding="utf-8")
    assert "html_design_timeout_seconds = 300" in config_path.read_text(encoding="utf-8")
    assert 'codex_binary = "codex"' in config_path.read_text(encoding="utf-8")
    assert 'claude_binary = "claude"' in config_path.read_text(encoding="utf-8")
    assert "debug_retention_run_count = 20" in config_path.read_text(encoding="utf-8")
    assert "low_confidence_evidence_threshold = 3" in config_path.read_text(encoding="utf-8")


def test_config_can_disable_debug_retention_with_zero(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "codex_session_paths = []",
                "claude_project_paths = []",
                "project_roots = []",
                'output_dir = "{}"'.format(tmp_path / "runs"),
                'state_dir = "{}"'.format(tmp_path / "state"),
                "debug_retention_run_count = 0",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.debug_retention_run_count == 0
