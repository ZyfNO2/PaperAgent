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


# ---------------------------------------------------------------------------
# Re6.4: Import novelty validators to register them
# ---------------------------------------------------------------------------

from . import novelty_validators  # noqa: E402, F401
