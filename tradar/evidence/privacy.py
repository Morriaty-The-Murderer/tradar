"""v0.1 PrivacyGate 调用点。"""

from __future__ import annotations

from typing import Protocol

from tradar.schemas import RawEvent


class PrivacyGateProtocol(Protocol):
    def filter(self, event: RawEvent) -> RawEvent:
        raise NotImplementedError


class PrivacyGate:
    def filter(self, event: RawEvent) -> RawEvent:
        return event
