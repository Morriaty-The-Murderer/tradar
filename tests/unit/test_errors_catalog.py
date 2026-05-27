from __future__ import annotations

import pytest

from tradar.errors.catalog import get_event_definition, require_registered_event


def test_error_catalog_registers_stable_warning_events() -> None:
    definition = get_event_definition("source.too_large")

    assert definition.event == "source.too_large"
    assert definition.severity == "P2"
    assert definition.recoverable is True


def test_error_catalog_registers_source_quota_warning() -> None:
    definition = get_event_definition("source.evidence_below_quota")

    assert definition.event == "source.evidence_below_quota"
    assert definition.severity == "P2"
    assert definition.recoverable is True


def test_error_catalog_rejects_unregistered_event_names() -> None:
    with pytest.raises(KeyError):
        require_registered_event("freeform.warning")
