"""PrivacyGate 调用点。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from tradar.schemas import RawEvent


@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: str
    replacement: str = ""


DEFAULT_REDACTION_RULES = [
    RedactionRule(
        name="secret_assignment",
        pattern=(
            r"\b[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}['\"]?"
        ),
    ),
]


class PrivacyGateProtocol(Protocol):
    def filter(self, event: RawEvent) -> RawEvent:
        raise NotImplementedError


class PrivacyGate:
    def __init__(
        self,
        redaction_rules: Sequence[RedactionRule] | None = None,
        replacement: str = "<REDACTED>",
    ) -> None:
        rules = list(DEFAULT_REDACTION_RULES if redaction_rules is None else redaction_rules)
        self._rules = [
            RedactionRule(
                rule.name,
                rule.pattern,
                rule.replacement or replacement,
            )
            for rule in rules
        ]

    @classmethod
    def from_patterns(
        cls,
        patterns: Sequence[str],
        replacement: str = "<REDACTED>",
    ) -> PrivacyGate:
        custom_rules = [
            RedactionRule(
                name=f"config_{index}",
                pattern=pattern,
                replacement=replacement,
            )
            for index, pattern in enumerate(patterns, start=1)
        ]
        return cls(
            redaction_rules=[*DEFAULT_REDACTION_RULES, *custom_rules],
            replacement=replacement,
        )

    def filter(self, event: RawEvent) -> RawEvent:
        title = event.title
        raw_text = event.raw_text
        warnings = list(event.parse_warnings)
        redacted_rule_names: list[str] = []

        for rule in self._rules:
            title, title_count = re.subn(rule.pattern, rule.replacement, title)
            raw_text, raw_count = re.subn(rule.pattern, rule.replacement, raw_text)
            if title_count or raw_count:
                redacted_rule_names.append(rule.name)

        if not redacted_rule_names:
            return event

        for name in redacted_rule_names:
            warning = f"privacy.redacted:{name}"
            if warning not in warnings:
                warnings.append(warning)

        return event.copy(
            update={
                "title": title,
                "raw_text": raw_text,
                "parse_warnings": warnings,
            }
        )
