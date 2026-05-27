"""Connector 通用契约。"""

from __future__ import annotations

from dataclasses import dataclass

CapabilityLevel = str


@dataclass(frozen=True)
class ConnectorCapabilities:
    title: CapabilityLevel
    timestamp: CapabilityLevel
    role: CapabilityLevel
    tool_calls: CapabilityLevel
    files: CapabilityLevel
    raw_text: CapabilityLevel
