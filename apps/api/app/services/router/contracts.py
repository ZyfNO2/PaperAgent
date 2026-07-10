"""StructuredOutputContract registry for Re6.2 Router Unification.

Every structured LLM node binds to one StructuredOutputContract.
The contract specifies the expected JSON schema, semantic validator,
allowed envelope shapes, and repair strategy.

Only the LATEST contract version for a given task_role is active.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from .model_policy import TaskRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contract model
# ---------------------------------------------------------------------------

RepairStrategy = Literal[
    "same_model_once",
    "formatter_once",
    "fallback_model_once",
    "fail",
]

FallbackBehavior = Literal["typed_failure", "heuristic_marked"]


class StructuredOutputContract(BaseModel):
    """A binding contract for structured LLM output.

    Each task_role + contract_id pair defines:
      - What JSON shape is expected (json_schema)
      - How to validate semantically (semantic_validator)
      - What repair strategy to use on failure
      - Whether to fail hard or mark as heuristic

    Contracts are registered in the CONTRACT_REGISTRY. Only the latest version
    for a given task_role is active (version uniqueness).
    """
    contract_id: str                          # e.g. "novelty-candidate/v1"
    task_role: TaskRole
    json_schema: dict[str, Any] = Field(default_factory=dict)  # JSON Schema
    semantic_validator: str = ""              # Validator function name in validators/
    accepted_envelopes: list[str] = Field(    # Which envelope shapes are accepted
        default_factory=lambda: ["content_json"]
    )
    repair_strategy: RepairStrategy = "same_model_once"
    max_repairs: int = 1                      # Hard upper bound (SOP §3.6: default 1)
    fallback_behavior: FallbackBehavior = "typed_failure"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ContractRegistry:
    """Thread-safe registry of StructuredOutputContracts.

    Key invariant: only the LATEST contract version for a given (task_role)
    is active. Registering a new contract for the same task_role supersedes
    the old one.
    """
    def __init__(self) -> None:
        self._by_id: dict[str, StructuredOutputContract] = {}
        self._by_role: dict[TaskRole, StructuredOutputContract] = {}

    def register(self, contract: StructuredOutputContract) -> None:
        """Register a contract. Supersedes any existing contract for the same task_role."""
        self._by_id[contract.contract_id] = contract
        self._by_role[contract.task_role] = contract
        logger.info("contract registered: %s → role=%s",
                     contract.contract_id, contract.task_role.value)

    def get_by_id(self, contract_id: str) -> StructuredOutputContract | None:
        """Look up a contract by its ID."""
        return self._by_id.get(contract_id)

    def get_by_role(self, task_role: TaskRole) -> StructuredOutputContract | None:
        """Get the active contract for a task role."""
        return self._by_role.get(task_role)

    def list_all(self) -> list[StructuredOutputContract]:
        """List all registered contracts."""
        return list(self._by_id.values())

    def list_roles(self) -> list[TaskRole]:
        """List task roles that have a registered contract."""
        return list(self._by_role.keys())

    def unregister(self, contract_id: str) -> bool:
        """Remove a contract by ID. Returns True if it existed."""
        contract = self._by_id.pop(contract_id, None)
        if contract is None:
            return False
        # Also remove from role index if it's the active one
        if self._by_role.get(contract.task_role) is contract:
            del self._by_role[contract.task_role]
        return True


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

_registry: ContractRegistry | None = None


def get_contract_registry() -> ContractRegistry:
    """Get or create the global contract registry (singleton)."""
    global _registry
    if _registry is None:
        _registry = ContractRegistry()
    return _registry


def reset_contract_registry() -> None:
    """Reset the registry (for testing)."""
    global _registry
    _registry = None
