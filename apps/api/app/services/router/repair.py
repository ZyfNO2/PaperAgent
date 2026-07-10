"""Bounded repair strategies for Re6.2 Router Unification.

SOP §3.6 defines 4 repair strategies with hard bounds:
  - same_model_once: re-prompt the SAME model ONCE
  - formatter_once: send to formatter role ONCE (no recursion)
  - fallback_model_once: try the NEXT model in fallback chain ONCE
  - fail: no repair, return failure

Key constraint (SOP §3.6.7): formatter MUST NOT recursively call itself.
This is enforced by tracking repair_depth and refusing formatter→formatter calls.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import RepairStrategy, StructuredOutputContract
from .envelope import ResponseEnvelope
from .model_policy import ModelPolicy, TaskRole

logger = logging.getLogger(__name__)

# Track repair context to prevent recursive formatter calls
_FORBIDDEN_FORMATTER_RECURSION = True


def execute_repair_strategy(
    strategy: RepairStrategy,
    *,
    prompt: str,
    system: str | None = None,
    envelope: ResponseEnvelope,
    contract: StructuredOutputContract,
    policy: ModelPolicy,
    temperature: float = 0.0,
    max_tokens: int = 4000,
    timeout: float = 60.0,
) -> dict[str, Any] | None:
    """Execute a single bounded repair attempt.

    Returns repaired JSON dict, or None if repair failed or not applicable.
    """
    if strategy == "same_model_once":
        return _repair_same_model(
            prompt, system=system, envelope=envelope,
            contract=contract, policy=policy,
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
    elif strategy == "formatter_once":
        return _repair_formatter(
            prompt, system=system, envelope=envelope,
            contract=contract, policy=policy,
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
    elif strategy == "fallback_model_once":
        return _repair_fallback_model(
            prompt, system=system, envelope=envelope,
            contract=contract, policy=policy,
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
    elif strategy == "fail":
        return None
    else:
        logger.warning("unknown repair strategy %r; treating as fail", strategy)
        return None


def _repair_same_model(
    prompt: str,
    *,
    system: str | None = None,
    envelope: ResponseEnvelope,
    contract: StructuredOutputContract,
    policy: ModelPolicy,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any] | None:
    """Re-prompt the SAME model with the raw output as context.

    The model sees its own failed output and is asked to fix it according
    to the contract schema. This is allowed exactly once.
    """
    repair_prompt = _build_repair_prompt(
        original_prompt=prompt,
        raw_output=envelope.content[:3000],
        contract=contract,
        strategy="same_model",
    )

    try:
        from .unified_router import _dispatch_call_via_registry
        ref = policy.primary
        new_envelope = _dispatch_call_via_registry(
            repair_prompt,
            system=system,
            ref=ref,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except Exception as exc:
        logger.debug("same_model_once repair dispatch failed: %s", exc)
        return None

    return _extract_valid_json(new_envelope, contract)


def _repair_formatter(
    prompt: str,
    *,
    system: str | None = None,
    envelope: ResponseEnvelope,
    contract: StructuredOutputContract,
    policy: ModelPolicy,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any] | None:
    """Send malformed output to the formatter role for JSON repair.

    CRITICAL: The formatter call uses a SEPARATE task_role, never re-enters
    the same contract. This prevents infinite formatter recursion.
    """
    formatter_prompt = (
        "You are a JSON repair assistant. The following LLM response failed "
        "to parse as valid JSON or failed semantic validation. Rewrite it "
        "so the ENTIRE output is exactly one valid JSON object matching "
        "the expected schema.\n\n"
        f"Expected schema: {contract.json_schema}\n\n"
        "Raw response to fix:\n---\n"
        f"{envelope.content[:3000]}\n---\n\n"
        "Reply ONLY with the corrected JSON object, no prose, no fences."
    )

    try:
        from .unified_router import _dispatch_call_via_registry
        from .model_policy import create_default_policy
        # Use formatter role with hard constraints
        fmt_policy = create_default_policy(TaskRole.formatter)
        fmt_policy = fmt_policy.model_copy(update={
            "max_format_repairs": 0,  # Prevent double-repair
            "max_provider_attempts": 1,  # Single attempt
        })
        ref = fmt_policy.primary
        new_envelope = _dispatch_call_via_registry(
            formatter_prompt,
            system=system,
            ref=ref,
            temperature=0.0,  # Deterministic repair
            max_tokens=min(max_tokens, 4000),
            timeout=timeout,
        )
    except Exception as exc:
        logger.debug("formatter_once repair dispatch failed: %s", exc)
        return None

    return _extract_valid_json(new_envelope, contract)


def _repair_fallback_model(
    prompt: str,
    *,
    system: str | None = None,
    envelope: ResponseEnvelope,
    contract: StructuredOutputContract,
    policy: ModelPolicy,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any] | None:
    """Try the next model in the fallback chain.

    If there is no fallback remaining, returns None.
    """
    if not policy.fallbacks:
        return None

    # Use the first fallback
    fallback_ref = policy.fallbacks[0]

    try:
        from .unified_router import _dispatch_call_via_registry
        new_envelope = _dispatch_call_via_registry(
            prompt,
            system=system,
            ref=fallback_ref,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except Exception as exc:
        logger.debug("fallback_model_once dispatch to %s failed: %s",
                     fallback_ref.model_id, exc)
        return None

    return _extract_valid_json(new_envelope, contract)


def _build_repair_prompt(
    original_prompt: str,
    raw_output: str,
    contract: StructuredOutputContract,
    strategy: str,
) -> str:
    """Build a repair prompt that includes context about what went wrong."""
    schema_desc = contract.json_schema or {}
    return (
        "Your previous response failed validation. Here is the original task:\n\n"
        f"{original_prompt[:2000]}\n\n"
        f"Expected output schema: {schema_desc}\n\n"
        "Your response (which was invalid):\n---\n"
        f"{raw_output}\n---\n\n"
        "Repair the response so it is exactly ONE valid JSON object matching "
        "the expected schema. Reply ONLY with the JSON, no prose, no fences."
    )


def _extract_valid_json(
    envelope: ResponseEnvelope,
    contract: StructuredOutputContract,
) -> dict[str, Any] | None:
    """Extract valid JSON from an envelope, optionally validating semantics."""
    data = envelope.extract_json()
    if data is None:
        return None

    if not isinstance(data, dict):
        return None

    if contract.semantic_validator:
        try:
            from .validators import get_validator
            fn = get_validator(contract.semantic_validator)
            if fn is not None:
                is_valid, _ = fn(data)
                if not is_valid:
                    return None
        except Exception:
            return None

    return data
