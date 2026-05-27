from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-llm-eval",
        action="store_true",
        default=False,
        help="Run optional golden report checks.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-llm-eval"):
        return

    skip_golden = pytest.mark.skip(reason="golden checks require --run-llm-eval")
    for item in items:
        if _is_golden_test(Path(str(item.path))):
            item.add_marker(skip_golden)


def _is_golden_test(path: Path) -> bool:
    return "golden" in path.parts and "tests" in path.parts
