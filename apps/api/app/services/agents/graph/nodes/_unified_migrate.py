"""Re7.6: shared helpers for migrating graph nodes to unified_router.

Usage in each node:
    from apps.api.app.services.agents.graph.nodes._unified_migrate import (
        call_structured, _use_unified,
    )

    result, prov = call_structured(
        prompt=user, system=system, task_role=TaskRole.evidence_critic,
        contract_id="sota-comparison/v1", validator_name="has_comparison_papers",
        env_flag="SOTA_USE_UNIFIED_ROUTER",
        fallback_fn=lambda: _heuristic(state),
        profile="fast_json", max_tokens=2000, timeout=30, expected="dict",
    )
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _use_unified(env_flag: str) -> bool:
    return os.environ.get(env_flag, "0") == "1"


def register_contract_if_missing(
    contract_id: str,
    task_role: Any,
    validator_name: str = "",
    repair_strategy: str = "fallback_model_once",
    fallback_behavior: str = "typed_failure",
) -> None:
    try:
        from apps.api.app.services.router.contracts import (
            StructuredOutputContract, get_contract_registry,
        )
        reg = get_contract_registry()
        if reg.get_by_id(contract_id) is None:
            reg.register(StructuredOutputContract(
                contract_id=contract_id,
                task_role=task_role,
                semantic_validator=validator_name,
                repair_strategy=repair_strategy,
                fallback_behavior=fallback_behavior,
            ))
    except Exception as exc:
        logger.debug("register_contract_if_missing %s failed: %s", contract_id, exc)


def call_structured(
    *,
    prompt: str,
    system: str | None = None,
    task_role: Any,
    contract_id: str,
    env_flag: str,
    fallback_fn: Callable[[], Any],
    validator_name: str = "",
    profile: str = "fast_json",
    max_tokens: int = 2000,
    timeout: float = 30.0,
    expected: str = "dict",
    schema_hint: str = "",
) -> tuple[Any, str]:
    """Call LLM via unified_router or legacy path.

    Returns (result, provider_tag).
    On failure, returns (fallback_fn(), "heuristic").
    """
    if _use_unified(env_flag):
        try:
            from apps.api.app.services.router import call_json_contract
            register_contract_if_missing(contract_id, task_role, validator_name)
            result = call_json_contract(
                prompt, system=system,
                task_role=task_role,
                max_tokens=max_tokens, timeout=timeout,
            )
            return result, "unified_router"
        except Exception as exc:
            logger.warning("unified_router failed for %s: %s — fallback", contract_id, exc)
            return fallback_fn(), "heuristic"
    else:
        try:
            from apps.api.app.services import llm_router
            out = llm_router.call_json(
                prompt, system=system, profile=profile,
                max_tokens=max_tokens, timeout=timeout,
                expected=expected, schema_hint=schema_hint,
            )
            if expected == "dict":
                return (out if isinstance(out, dict) else fallback_fn()), profile
            elif expected == "list":
                if isinstance(out, list):
                    return out, profile
                if isinstance(out, dict):
                    for key in ("results", "items", "candidates", "verdicts"):
                        if isinstance(out.get(key), list):
                            return out[key], profile
                    return [out], profile
                return fallback_fn(), "heuristic"
            return out, profile
        except Exception as exc:
            logger.warning("legacy LLM failed for %s: %s — fallback", contract_id, exc)
            return fallback_fn(), "heuristic"
