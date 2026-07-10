"""Unified Router for Re6.2 -- call_with_contract + ContractResult.

The unified router replaces llm_router.call_json() with a contract-driven
dispatch chain: ModelPolicy → Provider dispatch → ResponseEnvelope →
JSON parse → semantic validation → bounded repair.

Every structured LLM call flows through call_with_contract().
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from .contracts import ContractRegistry, StructuredOutputContract, get_contract_registry
from .envelope import ResponseEnvelope
from .model_policy import ModelPolicy, ProviderModelRef, TaskRole
from .repair import execute_repair_strategy

logger = logging.getLogger(__name__)


class ContractResult(BaseModel):
    """Result of a contract-driven LLM call.

    Contains the full provenance chain so the caller can inspect
    which providers were tried, how many repairs were needed, and
    whether the result is genuine or a heuristic fallback.
    """
    success: bool = False
    content: Any = None                    # Parsed JSON or text
    envelope: ResponseEnvelope | None = None
    contract_id: str = ""
    repair_count: int = 0
    provider_chain: list[str] = Field(default_factory=list)
    heuristic_fallback: bool = False
    error: str | None = None
    call_id: str = ""                      # Unique per-call trace ID

    @property
    def is_heuristic(self) -> bool:
        return self.heuristic_fallback

    @property
    def content_json(self) -> dict[str, Any] | None:
        if isinstance(self.content, dict):
            return self.content
        if self.envelope and self.envelope.has_valid_json_content():
            return self.envelope.extract_json()
        return None


# ---------------------------------------------------------------------------
# Provider dispatch (calls existing llm.py adapters)
# ---------------------------------------------------------------------------

def _dispatch_call(
    prompt: str,
    *,
    system: str | None = None,
    ref: ProviderModelRef,
    temperature: float = 0.0,
    max_tokens: int = 4000,
    timeout: float = 60.0,
) -> ResponseEnvelope:
    """Dispatch a single LLM call and normalize to ResponseEnvelope.

    Uses existing llm.py chat functions, then wraps result into an envelope.
    """
    from apps.api.app.services import llm as _llm

    request_id = str(uuid.uuid4())[:8]
    provider_id = ref.provider_id

    try:
        raw = _llm._chat_openai_compat_once(
            prompt,
            system=system,
            model=ref.model_id,
            api_key="",  # Will be resolved by the provider adapter
            base_url="",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except Exception:
        raise

    if not raw:
        raise ValueError(f"empty response from {ref.model_id}")

    envelope = ResponseEnvelope(
        provider_id=provider_id,
        model_id=ref.model_id,
        request_id=request_id,
        content=raw,
        raw_shape="openai_chat",
    )
    return envelope


def _dispatch_call_via_registry(
    prompt: str,
    *,
    system: str | None = None,
    ref: ProviderModelRef,
    temperature: float = 0.0,
    max_tokens: int = 4000,
    timeout: float = 60.0,
) -> ResponseEnvelope:
    """Dispatch through the provider registry for proper routing.

    Falls back to _dispatch_call if registry is not configured.
    """
    from apps.api.app.services import llm as _llm

    request_id = str(uuid.uuid4())[:8]

    # Route based on model_id
    model = ref.model_id
    try:
        if model == "deepseek-v4-flash":
            # Use deepseek path with provider registry fallback
            raw = _llm._chat_deepseek(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif model == "big-pickle":
            raw = _llm._chat_opencode(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        else:
            raise ValueError(f"unknown model_id: {model}")
    except Exception as exc:
        raise ValueError(f"dispatch failed for {model}: {exc}") from exc

    if not raw:
        raise ValueError(f"empty response from {ref.model_id}")

    return ResponseEnvelope(
        provider_id=ref.provider_id,
        model_id=ref.model_id,
        request_id=request_id,
        content=raw,
        raw_shape="openai_chat",
    )


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------

def _run_semantic_validator(
    data: dict[str, Any],
    contract: StructuredOutputContract,
) -> tuple[bool, str | None]:
    """Run the contract's semantic validator on parsed JSON data.

    Returns (is_valid, error_message).
    """
    validator_name = contract.semantic_validator
    if not validator_name:
        return True, None

    try:
        from .validators import get_validator
        fn = get_validator(validator_name)
        if fn is None:
            logger.debug("semantic validator %r not found; skipping", validator_name)
            return True, None
        return fn(data)
    except Exception as exc:
        logger.warning("semantic validator %r raised: %s", validator_name, exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def call_with_contract(
    prompt: str,
    *,
    system: str | None = None,
    contract_id: str | None = None,
    task_role: TaskRole | None = None,
    policy: ModelPolicy | None = None,
    contract: StructuredOutputContract | None = None,
    temperature: float | None = None,
    max_tokens: int = 4000,
    timeout: float = 60.0,
    registry: ContractRegistry | None = None,
) -> ContractResult:
    """Execute a contract-driven LLM call with bounded repair.

    Flow:
      1. Resolve contract + policy
      2. Dispatch to primary provider → envelope
      3. Parse JSON from envelope
      4. Run semantic validator
      5. If invalid → bounded repair (max 1 attempt)
      6. If repair fails → fallback provider
      7. If all fail → typed_failure or heuristic_marked

    Args:
        prompt: The user/system prompt for the LLM.
        system: Optional system prompt.
        contract_id: Look up contract by ID.
        task_role: Look up contract and policy by role.
        policy: Explicit ModelPolicy (overrides role default).
        contract: Explicit StructuredOutputContract.
        temperature: Override policy temperature.
        max_tokens: Max output tokens.
        timeout: LLM call timeout in seconds.
        registry: Contract registry (uses global default if None).

    Returns:
        ContractResult with full provenance.
    """
    reg = registry or get_contract_registry()

    # Resolve contract
    if contract is None:
        if contract_id:
            contract = reg.get_by_id(contract_id)
        elif task_role:
            contract = reg.get_by_role(task_role)
        if contract is None:
            raise ValueError(
                "no contract found; provide contract_id, task_role, or contract object"
            )

    # Resolve policy
    if policy is None:
        if task_role is None:
            task_role = contract.task_role
        from .model_policy import create_default_policy
        policy = create_default_policy(task_role)

    temp = policy.temperature if temperature is None else temperature
    call_id = str(uuid.uuid4())[:12]
    provider_chain: list[str] = []
    repair_count = 0

    # Try primary + fallbacks
    all_refs = policy.all_refs()
    last_envelope: ResponseEnvelope | None = None
    last_error: str | None = None

    for attempt_idx, ref in enumerate(all_refs):
        if attempt_idx >= policy.max_provider_attempts:
            break

        provider_chain.append(f"{ref.provider_id}/{ref.model_id}")
        logger.debug("call_with_contract %s: attempt %d → %s/%s",
                     call_id, attempt_idx + 1, ref.provider_id, ref.model_id)

        try:
            envelope = _dispatch_call_via_registry(
                prompt, system=system, ref=ref,
                temperature=temp, max_tokens=max_tokens, timeout=timeout,
            )
            last_envelope = envelope
        except Exception as exc:
            last_error = str(exc)
            logger.debug("call_with_contract %s: dispatch failed: %s", call_id, exc)
            continue

        # Try to parse JSON from envelope
        data = envelope.extract_json()
        if data is None:
            # Envelope has content but not valid JSON → try repair
            if repair_count < policy.max_format_repairs:
                repaired = execute_repair_strategy(
                    strategy="formatter_once",
                    prompt=prompt,
                    system=system,
                    envelope=envelope,
                    contract=contract,
                    policy=policy,
                    temperature=temp,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                repair_count += 1
                if repaired is not None:
                    data = repaired
                    last_envelope = ResponseEnvelope(
                        provider_id=ref.provider_id,
                        model_id=ref.model_id,
                        content=repaired if isinstance(repaired, str) else "",
                        raw_shape="custom",
                    )
            if data is None:
                last_error = f"JSON parse failed after {repair_count} repairs"
                continue

        # Run semantic validator
        if isinstance(data, dict) and contract.semantic_validator:
            is_valid, err = _run_semantic_validator(data, contract)
            if not is_valid:
                if repair_count < contract.max_repairs:
                    strategy = contract.repair_strategy
                    repaired = execute_repair_strategy(
                        strategy=strategy,
                        prompt=prompt,
                        system=system,
                        envelope=last_envelope,
                        contract=contract,
                        policy=policy,
                        temperature=temp,
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                    repair_count += 1
                    if repaired is not None and isinstance(repaired, dict):
                        is_valid2, _ = _run_semantic_validator(repaired, contract)
                        if is_valid2:
                            return ContractResult(
                                success=True,
                                content=repaired,
                                envelope=last_envelope,
                                contract_id=contract.contract_id,
                                repair_count=repair_count,
                                provider_chain=provider_chain,
                                call_id=call_id,
                            )
                last_error = err or "semantic validation failed"
                continue

        # Success
        return ContractResult(
            success=True,
            content=data,
            envelope=last_envelope,
            contract_id=contract.contract_id,
            repair_count=repair_count,
            provider_chain=provider_chain,
            call_id=call_id,
        )

    # All providers exhausted
    if policy.allow_heuristic:
        logger.warning("call_with_contract %s: all providers failed, "
                       "returning heuristic fallback", call_id)
        return ContractResult(
            success=False,
            content=last_envelope.content if last_envelope else None,
            envelope=last_envelope,
            contract_id=contract.contract_id,
            repair_count=repair_count,
            provider_chain=provider_chain,
            heuristic_fallback=True,
            error=last_error,
            call_id=call_id,
        )

    if contract.fallback_behavior == "heuristic_marked":
        logger.warning("call_with_contract %s: fallback_behavior=heuristic_marked, "
                       "returning partial result", call_id)
        return ContractResult(
            success=False,
            content=last_envelope.content if last_envelope else None,
            envelope=last_envelope,
            contract_id=contract.contract_id,
            repair_count=repair_count,
            provider_chain=provider_chain,
            heuristic_fallback=True,
            error=last_error,
            call_id=call_id,
        )

    # typed_failure
    return ContractResult(
        success=False,
        content=None,
        envelope=last_envelope,
        contract_id=contract.contract_id,
        repair_count=repair_count,
        provider_chain=provider_chain,
        error=last_error or "all providers exhausted",
        call_id=call_id,
    )


def call_json_contract(
    prompt: str,
    *,
    system: str | None = None,
    task_role: TaskRole,
    temperature: float | None = None,
    max_tokens: int = 4000,
    timeout: float = 60.0,
    raise_on_failure: bool = True,
) -> dict[str, Any] | None:
    """Convenience wrapper: call_with_contract, return JSON dict or raise.

    This is the drop-in replacement for call_json_with_validation()
    and llm_router.call_json() for structured output nodes.
    """
    result = call_with_contract(
        prompt=prompt,
        system=system,
        task_role=task_role,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )

    if result.success and isinstance(result.content, dict):
        return result.content

    if result.heuristic_fallback and not raise_on_failure:
        if isinstance(result.content, dict):
            return result.content
        return None

    if raise_on_failure:
        raise RuntimeError(
            f"call_json_contract failed for role={task_role.value}: "
            f"{result.error or 'unknown error'}, "
            f"provider_chain={result.provider_chain}, "
            f"repairs={result.repair_count}"
        )

    return None
