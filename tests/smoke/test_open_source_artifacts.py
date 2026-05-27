from __future__ import annotations

import tomllib
from pathlib import Path

from tradar.config.loader import load_config


def test_example_config_loads_without_real_machine_paths() -> None:
    config_path = Path("examples/config.toml")
    config = load_config(config_path)

    assert config.config_path == config_path
    assert config.output_dir == Path("~/.local/share/tradar/runs").expanduser()
    assert config.state_dir == Path("~/.local/share/tradar").expanduser()
    assert not any("/Users/" in raw for raw in config_path.read_text(encoding="utf-8").splitlines())


def test_public_project_metadata_uses_tradar_only() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "tradar"
    assert pyproject["project"]["scripts"] == {"tradar": "tradar.cli.app:app"}
    assert pyproject["tool"]["mypy"]["packages"] == ["tradar"]
