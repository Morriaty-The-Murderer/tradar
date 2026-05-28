from __future__ import annotations

import tomllib
from pathlib import Path

from tradar.config.loader import load_config


def _assert_example_config_is_public_safe(config_path: Path) -> None:
    text = config_path.read_text(encoding="utf-8")
    config = load_config(config_path)

    assert config.output_dir == Path("~/.local/share/tradar/runs").expanduser()
    assert config.state_dir == Path("~/.local/share/tradar").expanduser()
    assert config.codex_binary == "codex"
    assert config.claude_binary == "claude"
    assert 'codex_binary = "codex"' in text
    assert 'claude_binary = "claude"' in text
    assert not any("/Users/" in raw for raw in text.splitlines())
    assert "<" not in text
    assert ">" not in text


def test_example_config_loads_without_real_machine_paths() -> None:
    config_path = Path("examples/config.toml")
    _assert_example_config_is_public_safe(config_path)

    config = load_config(config_path)
    assert config.config_path == config_path


def test_v0_2_example_configs_cover_minimal_and_full_first_run_paths() -> None:
    minimal = Path("examples/minimal.toml")
    full = Path("examples/full.toml")

    _assert_example_config_is_public_safe(minimal)
    _assert_example_config_is_public_safe(full)

    minimal_config = load_config(minimal)
    full_config = load_config(full)

    assert minimal_config.codex_session_paths == []
    assert minimal_config.claude_project_paths == []
    assert full_config.codex_session_paths
    assert full_config.claude_project_paths
    assert full_config.project_roots


def test_public_project_metadata_uses_tradar_only() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "tradar"
    assert pyproject["project"]["scripts"] == {"tradar": "tradar.cli.app:app"}
    assert pyproject["tool"]["mypy"]["packages"] == ["tradar"]


def test_public_package_metadata_is_ready_for_distribution() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["version"] == "0.2.0"
    assert project["license"] == "MIT"
    assert project["keywords"] == ["agent", "local-first", "productivity", "traces"]
    assert "Development Status :: 3 - Alpha" in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert project["urls"]["Repository"].startswith("https://github.com/")
    assert project["urls"]["Issues"].startswith("https://github.com/")


def test_source_distribution_excludes_local_only_paths() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    excludes = set(pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"])

    assert "/.git" in excludes
    assert "/private" in excludes
    assert "/.venv" in excludes
    assert "/.pytest_cache" in excludes


def test_release_workflow_builds_smoke_tests_and_publishes_with_trusted_publishing() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "tags:" in workflow
    assert "v*.*.*" in workflow
    assert "id-token: write" in workflow
    assert "uv build" in workflow
    assert "dist/*.whl" in workflow
    assert "dist/*.tar.gz" in workflow
    assert "uv publish" in workflow


def test_privacy_docs_describe_first_public_use_controls() -> None:
    privacy = Path("docs/privacy.md").read_text(encoding="utf-8")

    assert "## Privacy Controls" in privacy
    assert "source allowlist" in privacy
    assert "evidence pack budget" in privacy
    assert "raw excerpts" in privacy
    assert "debug artifacts" in privacy
