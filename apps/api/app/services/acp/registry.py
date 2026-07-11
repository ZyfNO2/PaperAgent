"""Re4.4: Capability Registry — registers and validates ACP capabilities.

Inspired by AutoResearchClaw mcp/registry.py MCPServerRegistry (MIT, B-level):
same list/get pattern, but for capabilities (not external servers).
"""
from __future__ import annotations

from typing import Any

from .capabilities import CAPABILITIES
from .errors import ACPError, invalid_params, unknown_capability


class CapabilityRegistry:
    """Registry of all declared ACP capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {
            c["name"]: c for c in CAPABILITIES
        }

    def get(self, name: str) -> dict[str, Any] | None:
        return self._capabilities.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._capabilities.values())

    def list_names(self) -> list[str]:
        return list(self._capabilities.keys())

    def validate_params(self, name: str, params: dict[str, Any]) -> ACPError | None:
        cap = self.get(name)
        if cap is None:
            return unknown_capability(name)
        required = cap["input_schema"].get("required", [])
        missing = [r for r in required if r not in params or params[r] is None]
        if missing:
            return invalid_params(name, missing)
        return None

    def get_permission(self, name: str) -> str | None:
        cap = self.get(name)
        return cap["permission"] if cap else None

    @property
    def count(self) -> int:
        return len(self._capabilities)


_registry: CapabilityRegistry | None = None


def get_registry() -> CapabilityRegistry:
    global _registry
    if _registry is None:
        _registry = CapabilityRegistry()
    return _registry
