"""ModelPolicy + TaskRole + ProviderModelRef for Re6.2 Router Unification.

Defines the per-task-role routing policy. Every structured node's LLM call
is governed by a ModelPolicy that specifies primary provider/model, fallback
chain, and repair bounds.

Re6.X global constraint: model_id MUST be one of {"deepseek-v4-flash", "big-pickle"}.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Global model whitelist (Re6.X constraint)
# ---------------------------------------------------------------------------

ALLOWED_MODEL_IDS: frozenset[str] = frozenset({"deepseek-v4-flash", "big-pickle", "mistral-medium-latest", "meta/llama-3.1-8b-instruct", "mistral-small-latest", "stepfun-ai/step-3.7-flash", "deepseek-ai/deepseek-v3", "z-ai/glm-4.5-flash", "moonshotai/kimi-k2.6", "qwen/qwen3-8b", "google/gemma-3-12b-it"})


# ---------------------------------------------------------------------------
# Task Role
# ---------------------------------------------------------------------------

class TaskRole(str, Enum):
    """Coarse-grained LLM task roles in the research pipeline."""
    structured_extract = "structured_extract"   # topic_parser, verifier, dataset_extractor
    search_control = "search_control"           # planner, SearchController, repair
    evidence_critic = "evidence_critic"         # low_bar, devils_advocate, novelty_review
    novelty_draft = "novelty_draft"             # innovation_extractor, contribution writing
    narrative_write = "narrative_write"         # narrative_builder, report phrasing
    rag_answer = "rag_answer"                   # RAG QA
    formatter = "formatter"                     # JSON repair


# Task role → default primary model
_DEFAULT_PRIMARY: dict[TaskRole, str] = {
    TaskRole.structured_extract: "deepseek-v4-flash",
    TaskRole.search_control: "deepseek-v4-flash",
    TaskRole.evidence_critic: "big-pickle",
    TaskRole.novelty_draft: "big-pickle",
    TaskRole.narrative_write: "big-pickle",
    TaskRole.rag_answer: "deepseek-v4-flash",
    TaskRole.formatter: "deepseek-v4-flash",
}


def default_primary_for_role(role: TaskRole) -> str:
    """Return the default primary model_id for a given task role."""
    return _DEFAULT_PRIMARY.get(role, "deepseek-v4-flash")


# ---------------------------------------------------------------------------
# ProviderModelRef
# ---------------------------------------------------------------------------

class ProviderModelRef(BaseModel):
    """Reference to a specific model on a specific provider.

    Both provider_id and model_id are validated:
    - model_id MUST be in ALLOWED_MODEL_IDS.
    """
    provider_id: str = ""       # OpenCode proxy provider_id
    model_id: str = ""          # "deepseek-v4-flash" | "big-pickle"

    @model_validator(mode="after")
    def _check_model_whitelist(self) -> "ProviderModelRef":
        if self.model_id and self.model_id not in ALLOWED_MODEL_IDS:
            raise ValueError(
                f"model_id '{self.model_id}' not in allowed list: "
                f"{sorted(ALLOWED_MODEL_IDS)}"
            )
        return self

    def __hash__(self) -> int:
        return hash((self.provider_id, self.model_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProviderModelRef):
            return False
        return self.provider_id == other.provider_id and self.model_id == other.model_id


# ---------------------------------------------------------------------------
# ModelPolicy
# ---------------------------------------------------------------------------

class ModelPolicy(BaseModel):
    """Per-role routing policy that governs LLM provider selection.

    Each task role has one active ModelPolicy. The router reads this policy
    to decide which provider/model to call, the fallback chain, and repair bounds.
    """
    role: TaskRole
    primary: ProviderModelRef
    fallbacks: list[ProviderModelRef] = Field(default_factory=list)
    contract_version: str = ""          # e.g. "novelty-candidate/v1"
    temperature: float = 0.0
    allow_heuristic: bool = False       # Allow heuristic fallback when all models fail
    max_provider_attempts: int = 2      # Max total provider calls including retries
    max_format_repairs: int = 1         # Max formatter repair attempts (hard-cap at 1)

    @model_validator(mode="after")
    def _validate_fallback_chain(self) -> "ModelPolicy":
        """Ensure fallback chain has no cycles and all models are in whitelist."""
        # Validate primary is in whitelist
        if self.primary.model_id not in ALLOWED_MODEL_IDS:
            raise ValueError(
                f"primary model_id '{self.primary.model_id}' not in allowed list"
            )

        # Validate fallbacks
        for fb in self.fallbacks:
            if fb.model_id not in ALLOWED_MODEL_IDS:
                raise ValueError(
                    f"fallback model_id '{fb.model_id}' not in allowed list"
                )

        # Detect cycles in fallback chain.
        # A→A (primary as first fallback = self-review) is ALLOWED once.
        # A→B→A, A→B→B, A→A→A are true cycles → REJECTED.
        seen: set[tuple[str, str]] = set()
        primary_key = (self.primary.provider_id, self.primary.model_id)
        seen.add(primary_key)

        for i, fb in enumerate(self.fallbacks):
            key = (fb.provider_id, fb.model_id)
            if key in seen:
                # Primary can appear exactly once as the FIRST fallback (self-review)
                # Otherwise it's a true cycle
                if key == primary_key and i == 0 and self.fallbacks.count(fb) == 1:
                    # self-review: primary appears as first and only fallback
                    continue
                raise ValueError(
                    f"circular fallback detected: {fb.model_id} appears "
                    f"more than once in the chain"
                )
            seen.add(key)

        return self

    @model_validator(mode="after")
    def _cap_format_repairs(self) -> "ModelPolicy":
        """Hard-cap format repairs at 1 (SOP §3.6)."""
        if self.max_format_repairs > 1:
            object.__setattr__(self, "max_format_repairs", 1)
        return self

    @model_validator(mode="after")
    def _cap_provider_attempts(self) -> "ModelPolicy":
        """Hard-cap provider attempts at 3 (primary + 2 fallbacks max)."""
        if self.max_provider_attempts > 3:
            object.__setattr__(self, "max_provider_attempts", 3)
        return self

    def all_refs(self) -> list[ProviderModelRef]:
        """Return [primary] + fallbacks in order."""
        return [self.primary] + list(self.fallbacks)

    def is_self_review(self) -> bool:
        """True if primary and ALL fallbacks use the same model_id."""
        if not self.fallbacks:
            return False
        model_id = self.primary.model_id
        return all(fb.model_id == model_id for fb in self.fallbacks)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_DEFAULT_FALLBACK_MAP: dict[str, str] = {
    "deepseek-v4-flash": "big-pickle",
    "big-pickle": "deepseek-v4-flash",
    "mistral-small-latest": "meta/llama-3.1-8b-instruct",
    "mistral-medium-latest": "mistral-small-latest",
    "meta/llama-3.1-8b-instruct": "mistral-small-latest",
}


def _pick_fallback(primary_model: str) -> str:
    """Deterministically pick a fallback model for a given primary."""
    fb = _DEFAULT_FALLBACK_MAP.get(primary_model)
    if fb and fb in ALLOWED_MODEL_IDS:
        return fb
    # Generic fallback: prefer big-pickle or deepseek-v4-flash
    for candidate in ("big-pickle", "deepseek-v4-flash", "mistral-small-latest"):
        if candidate != primary_model and candidate in ALLOWED_MODEL_IDS:
            return candidate
    return primary_model


def create_default_policy(role: TaskRole, provider_id: str = "opencode") -> ModelPolicy:
    """Create a sensible default ModelPolicy for a given task role.

    Uses the role→model mapping from §3.2 of the R6.2 SOP.
    """
    primary_model = default_primary_for_role(role)
    fallback_model = _pick_fallback(primary_model)

    return ModelPolicy(
        role=role,
        primary=ProviderModelRef(provider_id=provider_id, model_id=primary_model),
        fallbacks=[
            ProviderModelRef(provider_id=provider_id, model_id=fallback_model),
        ],
    )
