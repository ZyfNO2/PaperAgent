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
import re
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
    # Re8.0 P1-3: also accept the case where LLM returns NEITHER field.
    # innovation_extractor_node has a complete heuristic fallback
    # (innovation_extractor.py:130-132) that produces a valid innovation
    # point from state when both fields are absent. Blocking at the
    # validator layer only wastes an LLM repair call that cannot
    # reconstruct missing content from an uninformative raw dict.
    if node_name == "innovation_extractor":
        if not missing:
            pass  # has innovation_points
        elif "stitching_plan" in data:
            missing = []  # stitching_plan alone is acceptable
        else:
            # Neither field present — let node-level heuristic handle it.
            missing = []
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


# ── Re8.1 WP3: Tailor output quality gates ─────────────────────────────────
# Non-blocking validation: logs warnings + attaches _validation field.
# Does NOT modify tailored_method schema or block the pipeline.
# Per spec.md WP3 "Semantic Field Validation" + "Assembly Plan Structure".

# Task 11.3: Generic substitute patterns (extensible list).
# Adding to this list does not require code changes elsewhere.
_GENERIC_SUBSTITUTE_PATTERNS: list[str] = [
    "添加注意力",
    "加入多尺度模块",
    "使用 Transformer",
    "应用 CNN",
    "引入残差连接",
    "采用 LSTM",
]

# Generic baseline strings (lowercased for exact match).
_GENERIC_BASELINE_STRINGS: set[str] = {
    "standard model",
    "baseline model",
    "default model",
    "generic model",
    "standard baseline",
    "default baseline",
    "baseline",
    "unknown",
}

# Default / placeholder texts that fail semantic traceability.
_DEFAULT_TEXTS: set[str] = {
    "tbd", "n/a", "default value", "todo", "placeholder",
    "unspecified", "未定", "待定", "未知", "暂定",
}

# Fields required to be non-empty (Task 11.1).
# Per spec.md WP3, these 7 fields are expected in tailored_method output.
# Note: task_definition / method_summary / dataset_and_metrics /
# reproduction_environment / limitations historically surface on
# SeedPaperCard, but WP3 validates them on tailored_method because the
# Tailor output should carry forward semantic content for downstream
# quality gates. core_method is referenced in spec.md diagnosis fields
# (tailored_method.core_method).
_TAILOR_REQUIRED_FIELDS: list[str] = [
    "task_definition",
    "method_summary",
    "dataset_and_metrics",
    "reproduction_environment",
    "limitations",
    "assembly_plan.description",  # nested via dotted notation
    "core_method",
]


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty for validation purposes."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _get_nested(data: dict, dotted_key: str) -> Any:
    """Get a nested value via dotted notation (e.g. assembly_plan.description)."""
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _detect_generic_substitute(text: str) -> bool:
    """Detect generic substitute patterns in text.

    Returns True if ``text`` contains any generic substitute pattern such as
    "添加注意力", "加入多尺度模块", "使用 Transformer", etc. The pattern list
    is extensible via ``_GENERIC_SUBSTITUTE_PATTERNS``.
    """
    if not isinstance(text, str):
        return False
    for pattern in _GENERIC_SUBSTITUTE_PATTERNS:
        if pattern in text:
            return True
    return False


def _validate_tailor_fields_non_empty(
    tailored_method: dict,
) -> tuple[bool, list[str]]:
    """Check that the 7 required Tailor fields are non-empty (Task 11.1).

    Required fields (per spec.md WP3):
      task_definition, method_summary, dataset_and_metrics,
      reproduction_environment, limitations, assembly_plan.description,
      core_method.

    Returns ``(all_non_empty, missing_fields)``.
    """
    if not isinstance(tailored_method, dict):
        return (False, list(_TAILOR_REQUIRED_FIELDS))
    missing: list[str] = []
    for field in _TAILOR_REQUIRED_FIELDS:
        value = _get_nested(tailored_method, field)
        if _is_empty(value):
            missing.append(field)
    return (len(missing) == 0, missing)


def _tokenize_for_jaccard(text: str) -> set[str]:
    """Tokenize text into a set of lowercase tokens for Jaccard similarity."""
    if not isinstance(text, str):
        return set()
    tokens = re.findall(r"[\w]+", text.lower())
    return set(tokens)


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a and not set_b:
        return 1.0  # both empty → identical
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _validate_semantic_traceability(
    tailored_method: dict,
    seed_papers: list,
) -> tuple[bool, list[str]]:
    """Check that field content is semantically traceable (Task 11.2).

    Checks:
      - Field content is not default text (TBD, N/A, default value, etc.)
      - Field content is not a simple title expansion
        (Jaccard similarity with title < 0.7)
      - Field content has reasonable length
        (method_summary > 50 chars, task_definition > 20 chars)

    Returns ``(is_traceable, issues)``.
    """
    if not isinstance(tailored_method, dict):
        return (False, ["tailored_method is not a dict"])

    issues: list[str] = []

    # Derive a reference title for similarity check.
    title = ""
    if isinstance(seed_papers, list) and seed_papers:
        first = seed_papers[0]
        if isinstance(first, dict):
            raw_input = first.get("raw_input") or {}
            title = (first.get("resolved_title")
                     or raw_input.get("title", "")
                     or "")
    if not title:
        pb = tailored_method.get("primary_baseline")
        if isinstance(pb, dict):
            title = pb.get("title", "") or ""
    title_tokens = _tokenize_for_jaccard(title) if title else set()

    # Fields checked for default text + title expansion + length.
    _TEXT_FIELDS: list[tuple[str, int]] = [
        ("task_definition", 20),    # (field, min_length)
        ("method_summary", 50),
    ]

    for field, min_len in _TEXT_FIELDS:
        value = tailored_method.get(field)
        if not isinstance(value, str):
            continue  # missing handled by non_empty check
        stripped = value.strip()
        if stripped.lower() in _DEFAULT_TEXTS:
            issues.append(f"{field}: default text '{stripped}'")
            continue
        if len(stripped) < min_len:
            issues.append(
                f"{field}: length {len(stripped)} < {min_len} chars"
            )
        if title_tokens:
            field_tokens = _tokenize_for_jaccard(stripped)
            sim = _jaccard_similarity(field_tokens, title_tokens)
            if sim >= 0.7:
                issues.append(
                    f"{field}: Jaccard {sim:.2f} with title (>=0.7, title expansion)"
                )

    # Check assembly_plan.description and core_method for default text only
    # (length / title-expansion checks focus on task_definition + method_summary
    # per spec; other fields only need to avoid placeholder text).
    for field in ("assembly_plan.description", "core_method"):
        value = _get_nested(tailored_method, field)
        if isinstance(value, str) and value.strip().lower() in _DEFAULT_TEXTS:
            issues.append(f"{field}: default text '{value.strip()}'")

    return (len(issues) == 0, issues)


def _validate_assembly_plan_baseline(
    assembly_plan: dict,
) -> tuple[bool, str]:
    """Check assembly_plan.baseline is valid (Task 12.1).

    - baseline field non-empty
    - baseline is not a generic substitute (e.g. "standard model")

    Returns ``(is_valid, issue)``. ``issue`` is empty string when valid.
    """
    if not isinstance(assembly_plan, dict):
        return (False, "assembly_plan is not a dict")
    baseline = assembly_plan.get("baseline")
    if _is_empty(baseline):
        return (False, "baseline is empty")
    if isinstance(baseline, str):
        stripped = baseline.strip().lower()
        if stripped in _GENERIC_BASELINE_STRINGS:
            return (False, f"baseline is generic: '{baseline}'")
        if _detect_generic_substitute(baseline):
            return (False, f"baseline is generic substitute: '{baseline}'")
    return (True, "")


def _validate_assembly_plan_modules(
    assembly_plan: dict,
) -> tuple[bool, list[str]]:
    """Check assembly_plan.modules list (Task 12.2).

    - modules is a non-empty list
    - each module has ``name`` and ``role`` fields

    Returns ``(is_valid, issues)``.
    """
    if not isinstance(assembly_plan, dict):
        return (False, ["assembly_plan is not a dict"])
    modules = assembly_plan.get("modules")
    if not isinstance(modules, list):
        return (False, ["modules is not a list"])
    if len(modules) == 0:
        return (False, ["modules is empty"])

    issues: list[str] = []
    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            issues.append(f"module[{i}] is not a dict")
            continue
        if _is_empty(m.get("name")):
            issues.append(f"module[{i}] missing 'name'")
        if _is_empty(m.get("role")):
            issues.append(f"module[{i}] missing 'role'")
    return (len(issues) == 0, issues)


def _validate_assembly_plan_connections(
    assembly_plan: dict,
) -> tuple[bool, list[str]]:
    """Check each module has a connection / integration_point (Task 12.3).

    Returns ``(is_valid, issues)``.
    """
    if not isinstance(assembly_plan, dict):
        return (False, ["assembly_plan is not a dict"])
    modules = assembly_plan.get("modules")
    if not isinstance(modules, list):
        return (False, ["modules is not a list (cannot check connections)"])

    issues: list[str] = []
    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            continue  # already reported by modules check
        has_connection = (
            not _is_empty(m.get("connection"))
            or not _is_empty(m.get("integration_point"))
        )
        if not has_connection:
            issues.append(
                f"module[{i}] ({m.get('name', '?')}) missing 'connection'/'integration_point'"
            )
    return (len(issues) == 0, issues)


def _validate_ablation_count(
    tailored_method: dict,
) -> tuple[bool, int]:
    """Check ablation_matrix / ablation_rows length >= 4 (Task 12.4).

    Returns ``(is_valid, actual_count)``.
    """
    ablation = tailored_method.get("ablation_matrix")
    if not isinstance(ablation, list):
        ablation = tailored_method.get("ablation_rows")
    count = len(ablation) if isinstance(ablation, list) else 0
    return (count >= 4, count)


def _validate_module_details(
    assembly_plan: dict,
) -> tuple[bool, list[str]]:
    """Check each module has source / io_semantics / failure_mode (Task 12.5).

    - source (来源)
    - io_semantics or input_output (IO 语义)
    - failure_mode (失败模式)

    Returns ``(is_valid, issues)``.
    """
    if not isinstance(assembly_plan, dict):
        return (False, ["assembly_plan is not a dict"])
    modules = assembly_plan.get("modules")
    if not isinstance(modules, list):
        return (False, ["modules is not a list (cannot check details)"])

    issues: list[str] = []
    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            continue
        name = m.get("name", f"module[{i}]")
        if _is_empty(m.get("source")):
            issues.append(f"module '{name}' missing 'source'")
        has_io = (
            not _is_empty(m.get("io_semantics"))
            or not _is_empty(m.get("input_output"))
        )
        if not has_io:
            issues.append(f"module '{name}' missing 'io_semantics'/'input_output'")
        if _is_empty(m.get("failure_mode")):
            issues.append(f"module '{name}' missing 'failure_mode'")
    return (len(issues) == 0, issues)


def validate_tailor_output(
    tailored_method: dict,
    seed_papers: list | None = None,
) -> dict[str, Any]:
    """Validate Tailor output quality gates (Task 11 + Task 12).

    Non-blocking: returns a validation report dict. Callers should
    attach this to ``tailored_method["_validation"]`` and log warnings,
    but NOT block the pipeline.

    Returns a dict with per-gate results and an ``overall_passed`` flag.
    """
    seed_papers = seed_papers or []
    report: dict[str, Any] = {}

    # Task 11.1: 7-field non-empty
    ne_passed, missing = _validate_tailor_fields_non_empty(tailored_method)
    report["field_non_empty"] = {"passed": ne_passed, "missing": missing}

    # Task 11.2: semantic traceability
    st_passed, st_issues = _validate_semantic_traceability(
        tailored_method, seed_papers
    )
    report["semantic_traceability"] = {"passed": st_passed, "issues": st_issues}

    # Task 11.3: generic substitute detection on key text fields
    generic_hits: list[str] = []
    for field in ("task_definition", "method_summary", "core_method"):
        value = tailored_method.get(field)
        if isinstance(value, str) and _detect_generic_substitute(value):
            generic_hits.append(field)
    report["generic_substitute"] = {
        "passed": len(generic_hits) == 0,
        "fields": generic_hits,
    }

    # Task 12: assembly_plan structure
    assembly_plan = tailored_method.get("assembly_plan")
    if not isinstance(assembly_plan, dict):
        assembly_plan = {}

    # Task 12.1: baseline
    bl_passed, bl_issue = _validate_assembly_plan_baseline(assembly_plan)
    report["assembly_plan_baseline"] = {"passed": bl_passed, "issue": bl_issue}

    # Task 12.2: modules
    mod_passed, mod_issues = _validate_assembly_plan_modules(assembly_plan)
    report["assembly_plan_modules"] = {"passed": mod_passed, "issues": mod_issues}

    # Task 12.3: connections
    conn_passed, conn_issues = _validate_assembly_plan_connections(assembly_plan)
    report["assembly_plan_connections"] = {
        "passed": conn_passed, "issues": conn_issues,
    }

    # Task 12.4: ablation count
    abl_passed, abl_count = _validate_ablation_count(tailored_method)
    report["ablation_count"] = {"passed": abl_passed, "count": abl_count}

    # Task 12.5: module details
    det_passed, det_issues = _validate_module_details(assembly_plan)
    report["module_details"] = {"passed": det_passed, "issues": det_issues}

    report["overall_passed"] = all([
        ne_passed,
        st_passed,
        len(generic_hits) == 0,
        bl_passed,
        mod_passed,
        conn_passed,
        abl_passed,
        det_passed,
    ])

    return report
