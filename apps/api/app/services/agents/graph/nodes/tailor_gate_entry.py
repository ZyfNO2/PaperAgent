"""Re8.2 Tailor Gate entrypoint.

A mode/policy short-circuit is not an evaluated pass. It retains legacy skip
behavior but must never populate or satisfy the Re8.2 reusable pass cache.
"""
from __future__ import annotations

from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from . import reflection_gate_reuse as _reuse
from . import reflection_gates as _legacy


def _without_skipped_tailor_pass(
    state: ResearchState,
) -> tuple[ResearchState, bool]:
    """Remove an obsolete cached skip pass from a shallow state copy."""
    passes = dict(state.get("last_gate_pass") or {})
    previous = passes.get(_legacy.GATE_TAILOR)
    if not isinstance(previous, dict) or previous.get("generated_by") != "skip":
        return state, False
    passes.pop(_legacy.GATE_TAILOR, None)
    sanitized: dict[str, Any] = dict(state)
    sanitized["last_gate_pass"] = passes
    return sanitized, True  # type: ignore[return-value]


def tailor_gate_node(state: ResearchState) -> dict[str, Any]:
    """Select legacy skip behavior or the Re8.2 evaluated/reuse path."""
    if not _legacy.is_react_reflection_enabled(state):
        return _legacy.tailor_gate_node(state)

    sanitized, removed_skip_cache = _without_skipped_tailor_pass(state)
    patch = dict(_reuse.tailor_gate_node(sanitized))
    if removed_skip_cache:
        passes = dict(patch.get("last_gate_pass") or sanitized.get("last_gate_pass") or {})
        current = passes.get(_legacy.GATE_TAILOR)
        if not isinstance(current, dict) or current.get("verdict") != "pass":
            passes[_legacy.GATE_TAILOR] = {}
            patch["last_gate_pass"] = passes
    return patch


__all__ = ["tailor_gate_node"]
