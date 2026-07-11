"""Semantic validator registry for Re6.2 Router Unification.

Validators are named functions that check the semantic validity of
parsed JSON output beyond mere schema compliance.

Each validator receives the parsed JSON dict and returns
(bool, str | None) = (is_valid, error_message).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Validator function signature
SemanticValidatorFn = Callable[[dict[str, Any]], tuple[bool, str | None]]

# Global registry
_validators: dict[str, SemanticValidatorFn] = {}


def register_validator(name: str) -> Callable[[SemanticValidatorFn], SemanticValidatorFn]:
    """Decorator to register a semantic validator function.

    Usage:
        @register_validator("novelty_candidate")
        def validate_novelty_candidate(data: dict) -> tuple[bool, str | None]:
            ...
    """
    def decorator(fn: SemanticValidatorFn) -> SemanticValidatorFn:
        _validators[name] = fn
        logger.debug("registered semantic validator: %s", name)
        return fn
    return decorator


def get_validator(name: str) -> SemanticValidatorFn | None:
    """Look up a semantic validator by name."""
    return _validators.get(name)


def list_validators() -> list[str]:
    """Return names of all registered validators."""
    return sorted(_validators.keys())


def reset_validators() -> None:
    """Clear all validators (for testing)."""
    _validators.clear()


# ---------------------------------------------------------------------------
# Built-in validators
# ---------------------------------------------------------------------------

@register_validator("non_empty_verdict")
def validate_non_empty_verdict(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that 'verdict' field exists and is non-empty."""
    verdict = data.get("verdict")
    if verdict is None:
        return False, "missing required field: verdict"
    if isinstance(verdict, str) and not verdict.strip():
        return False, "verdict is empty string"
    return True, None


@register_validator("has_innovation_points")
def validate_has_innovation_points(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that innovation_points exists and is a non-empty list."""
    points = data.get("innovation_points")
    if points is None:
        return False, "missing required field: innovation_points"
    if not isinstance(points, list):
        return False, f"innovation_points must be list, got {type(points).__name__}"
    if len(points) == 0:
        return False, "innovation_points is empty"
    return True, None


@register_validator("has_work_packages")
def validate_has_work_packages(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that work_packages exists and is a non-empty list."""
    wp = data.get("work_packages")
    if wp is None:
        return False, "missing required field: work_packages"
    if not isinstance(wp, list):
        return False, f"work_packages must be list, got {type(wp).__name__}"
    if len(wp) == 0:
        return False, "work_packages is empty"
    return True, None


@register_validator("non_empty_narrative")
def validate_non_empty_narrative(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate narrative output has at least one content-bearing field."""
    has_content = any(
        isinstance(data.get(k), str) and data.get(k, "").strip()
        for k in ("nick_model_name", "narrative_summary")
    )
    has_list = any(
        isinstance(data.get(k), list) and len(data.get(k, [])) > 0
        for k in ("three_problems", "narrative_sections")
    )
    if not has_content and not has_list:
        return False, "narrative output has no content-bearing fields"
    return True, None


@register_validator("valid_score_range")
def validate_valid_score_range(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that 'score' is numeric and in [0, 10]."""
    score = data.get("score")
    if score is None:
        return True, None  # Optional field
    if not isinstance(score, (int, float)):
        return False, f"score must be numeric, got {type(score).__name__}"
    if score < 0 or score > 10:
        return False, f"score {score} out of range [0, 10]"
    return True, None


@register_validator("valid_overall_verdict")
def validate_valid_overall_verdict(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate overall_verdict is one of ACCEPT, MINOR_REVISION, REJECT."""
    verdict = data.get("overall_verdict")
    if verdict is None:
        return False, "missing required field: overall_verdict"
    allowed = {"ACCEPT", "MINOR_REVISION", "REJECT"}
    if verdict not in allowed:
        return False, f"overall_verdict must be one of {allowed}, got {verdict!r}"
    return True, None


@register_validator("has_optimization_paths")
def validate_has_optimization_paths(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that optimization_paths/directions exists and is non-empty."""
    paths = data.get("optimization_paths") or data.get("optimization_directions")
    if paths is None:
        return False, "missing optimization_paths"
    if isinstance(paths, dict):
        paths = paths.get("optimization_paths") or []
    if not isinstance(paths, list) or len(paths) == 0:
        return False, "optimization_paths empty"
    return True, None


@register_validator("has_comparison_papers")
def validate_has_comparison_papers(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that comparison_papers exists and is non-empty."""
    papers = data.get("comparison_papers")
    if papers is None:
        return False, "missing comparison_papers"
    if not isinstance(papers, list):
        return False, f"comparison_papers must be list, got {type(papers).__name__}"
    if len(papers) == 0:
        return False, "comparison_papers empty"
    return True, None


@register_validator("valid_topic_atoms")
def validate_valid_topic_atoms(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate topic_atoms output: domain is a string and at least one axis is non-empty."""
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"

    domain = data.get("domain")
    if domain is None:
        return False, "missing required field: domain"
    if isinstance(domain, list):
        domain = next((str(x).strip().lower() for x in domain if str(x).strip()), "unknown")
    if not isinstance(domain, str):
        return False, f"domain must be a string, got {type(domain).__name__}"
    if not domain.strip():
        return False, "domain is empty"

    has_axis = any(
        isinstance(data.get(k), list) and len(data.get(k, [])) > 0
        for k in ("method", "object", "task", "scenario")
    )
    if not has_axis:
        return False, "topic_atoms has no non-empty method/object/task/scenario"

    return True, None


@register_validator("valid_search_plan")
def validate_valid_search_plan(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate search-plan/v1 output: non-empty queries list with valid tools/rounds."""
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"

    queries = data.get("queries")
    if not isinstance(queries, list):
        return False, f"queries must be a list, got {type(queries).__name__}"
    if not queries:
        return False, "queries list is empty"

    valid_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                   "huggingface", "core", "datacite", "pubmed"}
    valid_rounds = {"broad", "focused", "repair", "seed_expansion"}
    for i, q in enumerate(queries):
        if not isinstance(q, dict):
            return False, f"queries[{i}] is not a dict"
        tool = q.get("tool")
        if tool not in valid_tools:
            return False, f"queries[{i}] has invalid tool: {tool!r}"
        query_text = q.get("query")
        if not isinstance(query_text, str) or not query_text.strip():
            return False, f"queries[{i}] missing non-empty query"

    rounds = data.get("rounds")
    if isinstance(rounds, str):
        rounds = [rounds]
    if not isinstance(rounds, list) or not rounds:
        return False, "rounds must be a non-empty list"
    for i, r in enumerate(rounds):
        if str(r).strip().lower() not in valid_rounds:
            return False, f"rounds[{i}] invalid: {r!r}"

    return True, None


@register_validator("valid_quality_filter_batch")
def validate_valid_quality_filter_batch(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate query-filter-batch/v1 output: list of {index, is_paper, reason}."""
    if not isinstance(data, list):
        return False, f"expected list, got {type(data).__name__}"
    if not data:
        return False, "empty filter batch"
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return False, f"item[{i}] is not a dict"
        idx = item.get("index")
        if not isinstance(idx, int):
            return False, f"item[{i}] index must be int, got {type(idx).__name__}"
        if not isinstance(item.get("is_paper"), bool):
            return False, f"item[{i}] is_paper must be bool"
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False, f"item[{i}] reason must be non-empty string"
    return True, None


@register_validator("valid_baseline_classification")
def validate_valid_baseline_classification(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate baseline-classify/v1 output: classifications with idx and role."""
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"
    classifications = data.get("classifications")
    if not isinstance(classifications, list):
        return False, f"classifications must be list, got {type(classifications).__name__}"
    if not classifications:
        return False, "classifications is empty"
    valid_roles = {"baseline", "parallel"}
    for i, item in enumerate(classifications):
        if not isinstance(item, dict):
            return False, f"classifications[{i}] is not a dict"
        idx = item.get("idx")
        if not isinstance(idx, int):
            return False, f"classifications[{i}] idx must be int, got {type(idx).__name__}"
        role = item.get("role")
        if role not in valid_roles:
            return False, f"classifications[{i}] role must be baseline/parallel, got {role!r}"
    return True, None


@register_validator("valid_search_decision")
def validate_valid_search_decision(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate search-decision/v1 output: action/tool/query/reason."""
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"
    action = data.get("action")
    if action not in {"search", "stop"}:
        return False, f"action must be 'search' or 'stop', got {action!r}"
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False, "reason must be non-empty string"
    if action == "search":
        tool = data.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            return False, "search decision requires non-empty tool"
        query = data.get("query")
        if not isinstance(query, str) or not query.strip():
            return False, "search decision requires non-empty query"
    return True, None


@register_validator("valid_dataset_repo_list")
def validate_valid_dataset_repo_list(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate dataset-repo-list/v1 output: non-empty list of dicts."""
    if not isinstance(data, list):
        return False, f"expected list, got {type(data).__name__}"
    if not data:
        return False, "empty dataset/repo list"
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return False, f"item[{i}] is not a dict"
    return True, None


@register_validator("valid_targeted_repair")
def validate_valid_targeted_repair(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate targeted-repair/v1 output: non-empty queries with valid tools."""
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"
    queries = data.get("queries")
    if not isinstance(queries, list):
        return False, f"queries must be list, got {type(queries).__name__}"
    if not queries:
        return False, "queries list is empty"
    valid_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                   "huggingface", "core", "datacite", "pubmed"}
    for i, q in enumerate(queries):
        if not isinstance(q, dict):
            return False, f"queries[{i}] is not a dict"
        tool = q.get("tool")
        if tool not in valid_tools:
            return False, f"queries[{i}] has invalid tool: {tool!r}"
        query_text = q.get("query")
        if not isinstance(query_text, str) or not query_text.strip():
            return False, f"queries[{i}] missing non-empty query"
    strategy = data.get("strategy")
    if strategy is not None and strategy not in {"synonym", "broaden", "switch_tool"}:
        return False, f"strategy must be synonym/broaden/switch_tool, got {strategy!r}"
    return True, None


# ---------------------------------------------------------------------------
# Re6.4: Import novelty validators to register them
# ---------------------------------------------------------------------------

from . import novelty_validators  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Re7.6: Verifier batch validator
# ---------------------------------------------------------------------------

from . import verification_validator  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Re7.6 D-09: Novelty draft validator
# ---------------------------------------------------------------------------

@register_validator("has_novelty_drafts")
def validate_has_novelty_drafts(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that novelty_drafts exists and is a non-empty list.

    Each draft must have status 'draft' or 'needs_evidence' — never 'accepted'.
    """
    drafts = data.get("novelty_drafts")
    if drafts is None:
        return False, "missing required field: novelty_drafts"
    if not isinstance(drafts, list):
        return False, f"novelty_drafts must be list, got {type(drafts).__name__}"
    if len(drafts) == 0:
        return False, "novelty_drafts is empty"
    forbidden = {"accepted", "under_review", "verified"}
    for i, d in enumerate(drafts):
        if not isinstance(d, dict):
            return False, f"novelty_drafts[{i}] must be dict"
        status = d.get("status", "")
        if status in forbidden:
            return False, f"novelty_drafts[{i}] has forbidden status '{status}' — must be draft or needs_evidence"
    return True, None
