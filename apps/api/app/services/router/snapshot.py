"""RunModelSnapshot for Re6.2 Router Unification.

An immutable record of every contract-driven LLM call. Snapshots are
generated at call time and stored for later replay, audit, and
cross-model consistency verification.

SOP §3.7: Snapshots MUST be immutable — no field can be changed after creation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .contracts import StructuredOutputContract
from .envelope import ResponseEnvelope, TokenUsage
from .model_policy import ModelPolicy, ProviderModelRef


class RunModelSnapshot(BaseModel):
    """Immutable record of a single contract-driven LLM call.

    Captures everything needed to reproduce the call: the policy used,
    the contract bound, which providers were tried, the final result,
    and timing/token data.

    Fields are frozen after creation (model_config frozen=True).
    """
    model_config = {"frozen": True}

    snapshot_id: str = ""                       # Unique snapshot ID
    call_id: str = ""                           # Matches ContractResult.call_id
    timestamp: str = ""                         # ISO 8601 creation time

    # Policy snapshot
    policy_role: str = ""                       # TaskRole value
    policy_primary: str = ""                    # "provider/model_id"
    policy_fallbacks: list[str] = Field(default_factory=list)
    policy_temperature: float = 0.0
    policy_max_attempts: int = 2
    policy_max_repairs: int = 1

    # Contract snapshot
    contract_id: str = ""
    contract_role: str = ""
    contract_repair_strategy: str = ""
    contract_fallback: str = ""

    # Execution provenance
    provider_chain: list[str] = Field(default_factory=list)
    final_provider: str = ""
    final_model: str = ""
    repair_count: int = 0

    # Result
    success: bool = False
    heuristic_fallback: bool = False
    error: str | None = None

    # Token usage (normalized)
    token_input: int = 0
    token_output: int = 0

    # Prompt hash (for dedup/cache)
    prompt_sha256: str = ""

    @classmethod
    def capture(
        cls,
        *,
        call_id: str,
        policy: ModelPolicy,
        contract: StructuredOutputContract,
        provider_chain: list[str],
        repair_count: int,
        success: bool,
        heuristic_fallback: bool = False,
        error: str | None = None,
        envelope: ResponseEnvelope | None = None,
        prompt_sha256: str = "",
    ) -> "RunModelSnapshot":
        """Create an immutable snapshot from a completed call."""
        now = datetime.now(timezone.utc).isoformat()
        usage = envelope.usage if envelope else TokenUsage()

        return cls(
            snapshot_id=f"snap-{call_id}",
            call_id=call_id,
            timestamp=now,
            policy_role=policy.role.value,
            policy_primary=f"{policy.primary.provider_id}/{policy.primary.model_id}",
            policy_fallbacks=[
                f"{fb.provider_id}/{fb.model_id}" for fb in policy.fallbacks
            ],
            policy_temperature=policy.temperature,
            policy_max_attempts=policy.max_provider_attempts,
            policy_max_repairs=policy.max_format_repairs,
            contract_id=contract.contract_id,
            contract_role=contract.task_role.value,
            contract_repair_strategy=contract.repair_strategy,
            contract_fallback=contract.fallback_behavior,
            provider_chain=provider_chain,
            final_provider=envelope.provider_id if envelope else "",
            final_model=envelope.model_id if envelope else "",
            repair_count=repair_count,
            success=success,
            heuristic_fallback=heuristic_fallback,
            error=error,
            token_input=usage.input_tokens,
            token_output=usage.output_tokens,
            prompt_sha256=prompt_sha256,
        )

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a compact summary dict for reporting."""
        return {
            "snapshot_id": self.snapshot_id,
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "contract": self.contract_id,
            "role": self.contract_role,
            "success": self.success,
            "heuristic": self.heuristic_fallback,
            "providers_tried": len(self.provider_chain),
            "repairs": self.repair_count,
            "tokens_in": self.token_input,
            "tokens_out": self.token_output,
            "error": self.error,
        }


class SnapshotStore:
    """In-memory store of RunModelSnapshots for the current run.

    Snapshots are immutable once captured. The store provides
    lookup by call_id and aggregate reporting.
    """
    def __init__(self) -> None:
        self._snapshots: dict[str, RunModelSnapshot] = {}

    def save(self, snapshot: RunModelSnapshot) -> None:
        """Store a snapshot (immutable; last-write wins per call_id)."""
        self._snapshots[snapshot.call_id] = snapshot

    def get(self, call_id: str) -> RunModelSnapshot | None:
        """Retrieve a snapshot by call_id."""
        return self._snapshots.get(call_id)

    def list_all(self) -> list[RunModelSnapshot]:
        """Return all snapshots sorted by timestamp."""
        return sorted(self._snapshots.values(), key=lambda s: s.timestamp)

    def list_by_role(self, role: str) -> list[RunModelSnapshot]:
        """Return snapshots for a specific contract role."""
        return [
            s for s in self._snapshots.values()
            if s.contract_role == role
        ]

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        snapshots = list(self._snapshots.values())
        if not snapshots:
            return {"total": 0}

        success = sum(1 for s in snapshots if s.success)
        heuristic = sum(1 for s in snapshots if s.heuristic_fallback)
        total_tokens_in = sum(s.token_input for s in snapshots)
        total_tokens_out = sum(s.token_output for s in snapshots)

        return {
            "total": len(snapshots),
            "success": success,
            "failure": len(snapshots) - success,
            "heuristic_fallbacks": heuristic,
            "total_repairs": sum(s.repair_count for s in snapshots),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
        }

    def clear(self) -> None:
        """Clear all snapshots (for testing)."""
        self._snapshots.clear()


# Global snapshot store
_store: SnapshotStore | None = None


def get_snapshot_store() -> SnapshotStore:
    """Get or create the global snapshot store (singleton)."""
    global _store
    if _store is None:
        _store = SnapshotStore()
    return _store


def reset_snapshot_store() -> None:
    """Reset the store (for testing)."""
    global _store
    _store = None
