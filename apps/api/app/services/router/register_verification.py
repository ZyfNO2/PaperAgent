"""Re7.6: Register verification-batch/v1 contract in the global registry."""
from __future__ import annotations

from .contracts import StructuredOutputContract, get_contract_registry
from .model_policy import TaskRole


def register_verification_contract() -> None:
    """Register the verification-batch/v1 contract if not already present."""
    reg = get_contract_registry()
    existing = reg.get_by_id("verification-batch/v1")
    if existing is not None:
        return
    contract = StructuredOutputContract(
        contract_id="verification-batch/v1",
        task_role=TaskRole.structured_extract,
        json_schema={
            "type": "array",
            "items": {
                "type": "object",
                "required": ["candidate_id", "verdict", "relation_to_topic"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "verdict": {"enum": ["accept", "weak_reject", "reject", "unresolved"]},
                    "relation_to_topic": {"enum": ["baseline", "parallel", "survey", "none"]},
                    "reason": {"type": "string"},
                    "hit_keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        semantic_validator="verification_batch",
        accepted_envelopes=["content_json"],
        repair_strategy="formatter_once",
        max_repairs=1,
        fallback_behavior="typed_failure",
    )
    reg.register(contract)
