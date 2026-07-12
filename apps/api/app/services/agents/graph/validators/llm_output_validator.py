"""Re5.X: LLM output schema validator + auto-repair.

Two-layer defense against malformed LLM outputs:

1. Schema validation: each node declares its expected output fields.
   If the LLM returns a dict with wrong keys (e.g. verify format
   leaking into feasibility), the validator catches it.

2. LLM-powered repair: when schema validation fails, the raw output
   is sent to the LLM with a repair prompt that includes the expected
   schema, asking it to extract the correct information and reformat.

This replaces the silent `isinstance(out, dict)` acceptance pattern
that allowed cross-node format contamination.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ── Schema registry: node_name → required_fields ──────────────────────────

_NODE_SCHEMAS: dict[str, dict[str, type]] = {
    "feasibility_assessor": {
        "verdict": str,
        "score": (int, float),
        "reason": str,
    },
    "innovation_extractor": {
        # top-level must have at least one of these
        "innovation_points": list,
    },
    "narrative_builder": {
        # at least one of these
        "nick_model_name": str,
        "narrative_summary": str,
        "three_problems": list,
    },
    "work_package": {
        "work_packages": list,
    },
    "devils_advocate": {
        "overall_verdict": str,
    },
    "optimization_advisor": {
        "optimization_directions": (list, dict),
    },
    "sota_matcher": {
        "comparison_papers": list,
    },
}

# ── Known "wrong node" signatures ─────────────────────────────────────────
# If a dict matches one of these signatures, it's clearly from another node.

_WRONG_NODE_SIGNATURES: list[dict[str, set[str]]] = [
    # verify node output
    {"keys": {"verdict", "hit_keywords", "relation_to_topic"}, "source": "verify"},
    {"keys": {"verdict", "hit_keywords", "relation_to_topic", "reason"}, "source": "verify"},
    # search agent output
    {"keys": {"action", "tool", "query", "reason"}, "source": "search_agent"},
]

# ── Repair prompt ─────────────────────────────────────────────────────────

_REPAIR_SYSTEM = (
    "你是JSON修复器。下面是一个LLM节点产生的错误格式输出。"
    "请根据期望的schema，从原始输出中提取正确信息，重新格式化为合法JSON。"
    "如果原始输出中缺少必要信息，用合理默认值填充。"
    "只输出JSON，不要输出其他内容。"
)

_REPAIR_TEMPLATE = """期望的输出格式 (node={node}):
{expected_fields}

原始输出 (可能来自错误的节点):
{raw_output}

请提取相关信息，输出符合期望格式的JSON。
如果原始输出中有 verdict=reject 但没有 score 字段，说明这是论文验证结果而非可行性评估——
请根据原始输出中的 verdict 和 relation_to_topic 推断合理的可行性分数。

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象。"""


def _check_wrong_node(data: dict[str, Any]) -> str | None:
    """Check if data matches a known wrong-node signature.

    Returns the source node name if matched, None otherwise.
    """
    data_keys = set(data.keys())
    for sig in _WRONG_NODE_SIGNATURES:
        if sig["keys"].issubset(data_keys):
            return sig["source"]
    return None


def validate_node_output(
    node_name: str,
    data: Any,
) -> tuple[bool, str | None]:
    """Validate that LLM output matches the expected schema for a node.

    Returns (is_valid, error_message).
    """
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"

    schema = _NODE_SCHEMAS.get(node_name)
    if schema is None:
        # No schema registered → accept any dict
        return True, None

    # Check for wrong-node contamination
    wrong_source = _check_wrong_node(data)
    if wrong_source:
        return False, (
            f"output matches {wrong_source} node signature "
            f"(keys={sorted(data.keys())}), not {node_name} schema"
        )

    # Check required fields
    missing: list[str] = []
    wrong_type: list[str] = []
    for field, expected_type in schema.items():
        if field not in data:
            missing.append(field)
        elif not isinstance(data[field], expected_type):
            wrong_type.append(
                f"{field}: expected {expected_type}, got {type(data[field]).__name__}"
            )

    # Special: allow "innovation_points" node to have stitching_plan instead
    # P3-2 fix: innovation_extractor accepts EITHER innovation_points OR
    # stitching_plan (the node has its own empty-list fallback at line 125).
    # Previously, LLM returning only stitching_plan triggered a confusing
    # "missing required fields: ['innovation_points']" warning + LLM repair.
    if node_name == "innovation_extractor":
        if not missing:
            pass  # has innovation_points
        elif "stitching_plan" in data:
            missing = []  # stitching_plan alone is acceptable
    elif missing and node_name == "narrative_builder":
        # narrative needs at least one of nick_model_name, narrative_summary, three_problems
        if any(k in data for k in ("nick_model_name", "narrative_summary", "three_problems")):
            missing = []

    if missing:
        return False, f"missing required fields: {missing}"
    if wrong_type:
        return False, f"type errors: {wrong_type}"

    return True, None


def repair_with_llm(
    node_name: str,
    raw_output: Any,
    *,
    profile: str = "fast_json",
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """Send malformed output to LLM for repair.

    Returns repaired dict or None if repair fails.
    """
    from apps.api.app.services.llm_router import call_json, LLMUnavailable

    schema = _NODE_SCHEMAS.get(node_name, {})
    expected_fields = json.dumps(
        {k: str(v) for k, v in schema.items()},
        ensure_ascii=False,
        indent=2,
    )

    raw_str = json.dumps(raw_output, ensure_ascii=False, default=str)[:3000]

    prompt = _REPAIR_TEMPLATE.format(
        node=node_name,
        expected_fields=expected_fields,
        raw_output=raw_str,
    )

    try:
        result = call_json(
            prompt,
            system=_REPAIR_SYSTEM,
            profile=profile,
            max_tokens=2000,
            expected="dict",
            timeout=timeout,
        )
        if isinstance(result, dict):
            # Verify the repaired output passes validation
            is_valid, _ = validate_node_output(node_name, result)
            if is_valid:
                logger.info(
                    "schema_repair: %s output repaired successfully", node_name
                )
                return result
            else:
                logger.warning(
                    "schema_repair: %s repair output still invalid: %s",
                    node_name,
                    _,
                )
                return result  # return anyway — better than heuristic
        return None
    except LLMUnavailable as exc:
        logger.warning("schema_repair: %s LLM repair failed: %s", node_name, exc)
        return None
    except Exception as exc:
        logger.warning("schema_repair: %s unexpected error: %s", node_name, exc)
        return None


def call_json_with_validation(
    prompt: str,
    *,
    system: str | None = None,
    node_name: str,
    profile: str = "fast_json",
    max_tokens: int = 2000,
    timeout: float = 30.0,
    fallback: Any | None = None,
    contract_id: str | None = None,
) -> Any:
    """Call LLM, validate output schema, auto-repair if needed.

    Re6.2: Delegates to call_json_contract when a contract is registered
    for the node's task_role. Falls back to legacy call_json otherwise.

    Re7.7: USE_CONTRACT_PATH env var (default "0") globally controls whether
    the contract path is attempted. When "0" (default), contract_id is
    ignored and all calls go through the legacy call_json(profile=...) path
    so that profile="fast_json"/"premium_review" → mistral is actually used.
    Set USE_CONTRACT_PATH=1 to re-enable the Re6.2 unified router.

    Flow:
      1. If contract_id provided AND USE_CONTRACT_PATH=1 → contract path
      2. Else → legacy call_json + schema validation + repair
      3. If invalid → send to LLM repair
      4. If repair fails → use fallback (heuristic) or raise

    Args:
        prompt: User prompt for the LLM
        system: System prompt
        node_name: Node name for schema lookup
        profile: LLM provider profile
        max_tokens: Max tokens for LLM response
        timeout: LLM call timeout
        fallback: Heuristic fallback value if all else fails
        contract_id: Optional contract ID for Re6.2 unified router

    Returns:
        Validated LLM output, or fallback, or raises LLMUnavailable
    """
    # Re6.2: Try contract-driven path first
    # Re7.7: USE_CONTRACT_PATH env (default "0") controls whether contract
    # path is used at all. When disabled, all calls go through legacy
    # call_json(profile=...) so the profile actually controls the provider.
    _use_contract = os.environ.get("USE_CONTRACT_PATH", "0").strip().lower() in ("1", "true", "yes")
    if contract_id and _use_contract:
        try:
            from apps.api.app.services.router import call_with_contract, TaskRole
            result = call_with_contract(
                prompt=prompt,
                system=system,
                contract_id=contract_id,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            if result.success and isinstance(result.content, dict):
                return result.content
            if result.heuristic_fallback:
                if isinstance(result.content, dict):
                    return result.content
                if fallback is not None:
                    return fallback
            if fallback is not None:
                return fallback
            logger.warning(
                "call_json_with_validation: %s contract call failed: %s",
                node_name, result.error,
            )
        except Exception as exc:
            logger.warning(
                "call_json_with_validation: %s contract path failed: %s, "
                "falling back to legacy",
                node_name, exc,
            )

    from apps.api.app.services.llm_router import call_json, LLMUnavailable

    # Step 1: Call LLM
    try:
        raw = call_json(
            prompt,
            system=system,
            profile=profile,
            max_tokens=max_tokens,
            expected="dict",
            timeout=timeout,
        )
    except LLMUnavailable:
        if fallback is not None:
            logger.warning(
                "call_json_with_validation: %s LLM failed, using fallback",
                node_name,
            )
            return fallback
        raise

    # Step 2: Validate
    is_valid, error = validate_node_output(node_name, raw)
    if is_valid:
        return raw

    # If wrong-node contamination detected, skip LLM repair — go straight to fallback
    wrong_source = _check_wrong_node(raw) if isinstance(raw, dict) else None
    if wrong_source:
        logger.warning(
            "call_json_with_validation: %s output is from %s node — skipping repair, using fallback",
            node_name,
            wrong_source,
        )
        if fallback is not None:
            return fallback

    logger.warning(
        "call_json_with_validation: %s schema validation failed: %s — attempting LLM repair",
        node_name,
        error,
    )

    # Step 3: LLM repair
    repaired = repair_with_llm(node_name, raw, profile=profile, timeout=timeout)
    if repaired is not None:
        return repaired

    # Step 4: Fallback
    if fallback is not None:
        logger.warning(
            "call_json_with_validation: %s repair failed, using fallback",
            node_name,
        )
        return fallback

    # Last resort: return raw (better than crash, caller should handle)
    logger.warning(
        "call_json_with_validation: %s no fallback, returning raw invalid output",
        node_name,
    )
    return raw
