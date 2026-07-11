"""Re7.6: verification-batch/v1 contract + semantic validator."""
from __future__ import annotations

from typing import Any

from . import register_validator


VALID_VERDICTS = frozenset({"accept", "weak_reject", "reject", "unresolved"})
VALID_RELATIONS = frozenset({"baseline", "parallel", "survey", "none"})


@register_validator("verification_batch")
def validate_verification_batch(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Semantic validator for verification-batch/v1 contract output.

    The verifier returns a list of verdicts as the top-level content.
    This validator runs on the list (not a dict), so the unified_router
    must handle list-type contracts.
    """
    if not isinstance(data, list):
        if isinstance(data, dict):
            for key in ("verdicts", "candidates", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                return False, "expected list of verdicts or dict with verdicts key"
        else:
            return False, f"expected list, got {type(data).__name__}"

    if not data:
        return False, "empty verdict list — no candidates resolved"

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return False, f"item[{i}] is not a dict"
        cid = item.get("candidate_id", "")
        if not cid:
            return False, f"item[{i}] missing candidate_id"
        verdict = item.get("verdict", "")
        if verdict not in VALID_VERDICTS:
            return False, f"item[{i}] invalid verdict: {verdict!r}"
        relation = item.get("relation_to_topic", "")
        if relation not in VALID_RELATIONS:
            return False, f"item[{i}] invalid relation_to_topic: {relation!r}"

    return True, None


def validate_verification_contract(data: Any) -> tuple[bool, str | None]:
    """Top-level validator: accepts list or normalised dict wrapping a list."""
    if isinstance(data, list):
        return validate_verification_batch({"verdicts": data})
    if isinstance(data, dict):
        return validate_verification_batch(data)
    return False, f"expected list or dict, got {type(data).__name__}"
