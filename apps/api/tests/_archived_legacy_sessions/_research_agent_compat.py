"""Compat shim for re04_entry — re-exports the Re02 helper symbols
the new Re04 entry needs (parse_topic, plan_tools_v2, synthesize_v2,
chat_json_strict, FAMILY_TO_ADAPTER).

Importing the whole `research_agent` module is expensive (~2700 lines)
so we lazy-load it.
"""
from __future__ import annotations

import importlib
from typing import Any

_mod = None


def _get_mod():
    global _mod
    if _mod is None:
        _mod = importlib.import_module("app.services.agents.research_agent")
    return _mod


# Re-exports the test/eval harness needs. Keep this list small.
__all__ = ["parse_topic", "plan_tools_v2", "synthesize_v2", "chat_json_strict",  # noqa: F822
           "FAMILY_TO_ADAPTER", "audit_candidates"]  # noqa: F822


def __getattr__(name: str) -> Any:
    if name == "FAMILY_TO_ADAPTER":
        from .retrieval_orchestrator import FAMILY_TO_ADAPTER
        return FAMILY_TO_ADAPTER
    if name == "chat_json_strict":
        mod = _get_mod()
        return getattr(mod, "_chat_json_strict")
    if name == "audit_candidates":
        from .evidence_review import audit_candidates
        return audit_candidates
    mod = _get_mod()
    return getattr(mod, name)

