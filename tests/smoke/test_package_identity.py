from __future__ import annotations

import importlib


def test_public_package_imports_as_tradar() -> None:
    module = importlib.import_module("tradar")

    assert module.__name__ == "tradar"


def test_console_scripts_point_to_tradar_package() -> None:
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["tradar"] == "tradar.cli.app:app"
    assert "radar" not in pyproject["project"]["scripts"]
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["tradar"]
    assert pyproject["tool"]["mypy"]["packages"] == ["tradar"]
