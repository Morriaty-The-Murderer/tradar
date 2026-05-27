"""Analyst JSON 输出校验和一次 schema repair。"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tradar.schemas import RadarReport


class AgentOutputSchemaError(Exception):
    """Analyst agent 输出无法修复为 RadarReport。"""

    def __init__(self, message: str, run_id: str = "", artifact_path: str = "") -> None:
        self.run_id = run_id
        self.artifact_path = artifact_path
        super().__init__(message)


class SchemaRepairAdapter:
    def repair(self, raw_text: str, error_message: str) -> str:
        raise NotImplementedError


class FixedSchemaRepairAdapter(SchemaRepairAdapter):
    def __init__(self, repaired_text: str) -> None:
        self.repaired_text = repaired_text
        self.calls = 0

    def repair(self, raw_text: str, error_message: str) -> str:
        self.calls += 1
        return self.repaired_text


def validate_or_repair_report(
    raw_text: str,
    repair_adapter: SchemaRepairAdapter | None = None,
) -> RadarReport:
    error_message = ""
    try:
        return RadarReport.parse_raw(raw_text)
    except (ValidationError, ValueError) as original_error:
        error_message = str(original_error)
        if repair_adapter is None:
            raise AgentOutputSchemaError(error_message) from original_error

    original_shape = _load_json_shape(raw_text)
    repaired_text = repair_adapter.repair(raw_text, error_message)

    try:
        repaired = RadarReport.parse_raw(repaired_text)
    except (ValidationError, ValueError) as repair_error:
        raise AgentOutputSchemaError(str(repair_error)) from repair_error

    _validate_repair_preserved_evidence(original_shape, repaired)
    return repaired


def _load_json_shape(raw_text: str) -> dict[str, Any]:
    try:
        import json

        loaded = json.loads(raw_text)
    except ValueError:
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _validate_repair_preserved_evidence(
    original_shape: dict[str, Any],
    repaired: RadarReport,
) -> None:
    original_cards = original_shape.get("opportunity_cards")
    if not isinstance(original_cards, list):
        return
    if not original_cards:
        return

    original_identities = [_card_identity(card) for card in original_cards]
    if len(repaired.opportunity_cards) != len(original_identities):
        raise AgentOutputSchemaError("schema repair changed opportunity card ranking")
    repaired_identities = [
        _repaired_card_identity(card, field)
        for card, (field, _value) in zip(
            repaired.opportunity_cards,
            original_identities,
            strict=True,
        )
    ]
    original_values = [value for _field, value in original_identities]
    if original_values and repaired_identities != original_values[: len(repaired_identities)]:
        raise AgentOutputSchemaError("schema repair changed opportunity card ranking")

    original_evidence_ids = _evidence_ids(original_cards)
    repaired_evidence_ids = []
    for card in repaired.opportunity_cards:
        repaired_evidence_ids.extend(card.evidence_ids)
    if original_evidence_ids and not set(repaired_evidence_ids).issubset(
        set(original_evidence_ids)
    ):
        raise AgentOutputSchemaError("schema repair added new evidence ids")


def _card_identity(card: Any) -> tuple[str, str]:
    if isinstance(card, dict):
        for field in ("title", "card_id", "one_sentence"):
            value = str(card.get(field) or "")
            if value:
                return field, value
    return "title", ""


def _repaired_card_identity(card: Any, field: str) -> str:
    return str(getattr(card, field, "") or "")


def _evidence_ids(cards: list[Any]) -> list[str]:
    evidence_ids: list[str] = []
    for card in cards:
        if isinstance(card, dict) and isinstance(card.get("evidence_ids"), list):
            evidence_ids.extend(str(value) for value in card["evidence_ids"])
    return evidence_ids
