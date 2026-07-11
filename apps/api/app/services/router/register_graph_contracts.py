"""Re7.6: Register all graph-node contracts for unified_router path.

Import this module once at app startup (or before graph execution) to make
all contract_id-based LLM calls in graph nodes resolve through the
unified_router dispatch chain.

Usage in main.py:
    from apps.api.app.services.router import register_graph_contracts
    register_graph_contracts()
"""
from __future__ import annotations

from .contracts import StructuredOutputContract, get_contract_registry
from .model_policy import TaskRole


def register_graph_contracts() -> None:
    """Register all graph-node contracts if not already present."""
    reg = get_contract_registry()

    contracts = [
        # Topic parser (dict-type output)
        StructuredOutputContract(
            contract_id="topic-parse/v1",
            task_role=TaskRole.structured_extract,
            semantic_validator="valid_topic_atoms",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Search agent decision (dict-type output).
        # Registered BEFORE search-plan/v1 because both use TaskRole.search_control
        # and the role-index keeps only the latest registration; search_agent uses
        # explicit contract_id so it is unaffected by role-index ordering.
        StructuredOutputContract(
            contract_id="search-decision/v1",
            task_role=TaskRole.search_control,
            semantic_validator="valid_search_decision",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Targeted repair (dict-type output).
        # Also uses TaskRole.search_control; registered before search-plan/v1.
        StructuredOutputContract(
            contract_id="targeted-repair/v1",
            task_role=TaskRole.search_control,
            semantic_validator="valid_targeted_repair",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Search planner (dict-type output)
        StructuredOutputContract(
            contract_id="search-plan/v1",
            task_role=TaskRole.search_control,
            semantic_validator="valid_search_plan",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Verifier (list-type output)
        StructuredOutputContract(
            contract_id="verification-batch/v1",
            task_role=TaskRole.structured_extract,
            semantic_validator="verification_batch",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Optimization advisor
        StructuredOutputContract(
            contract_id="optimization-advisory/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="has_optimization_paths",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # SOTA matcher
        StructuredOutputContract(
            contract_id="sota-comparison/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="has_comparison_papers",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Baseline classifier (dict-type)
        StructuredOutputContract(
            contract_id="baseline-classify/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="valid_baseline_classification",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Quality filter (list-type)
        StructuredOutputContract(
            contract_id="query-filter-batch/v1",
            task_role=TaskRole.structured_extract,
            semantic_validator="valid_quality_filter_batch",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Work package
        StructuredOutputContract(
            contract_id="work-package/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="has_work_packages",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Dataset repo extraction (list-type)
        StructuredOutputContract(
            contract_id="dataset-repo-list/v1",
            task_role=TaskRole.structured_extract,
            semantic_validator="valid_dataset_repo_list",
            repair_strategy="formatter_once",
            fallback_behavior="typed_failure",
        ),
        # Individual dataset/repo from content.py (dict-type)
        StructuredOutputContract(
            contract_id="dataset-repo-extraction/v1",
            task_role=TaskRole.structured_extract,
            semantic_validator="",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Devils advocate
        StructuredOutputContract(
            contract_id="devils-advocate/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="valid_overall_verdict",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Feasibility check
        StructuredOutputContract(
            contract_id="feasibility-check/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="non_empty_verdict",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Innovation extraction
        StructuredOutputContract(
            contract_id="innovation-extraction/v1",
            task_role=TaskRole.novelty_draft,
            semantic_validator="has_innovation_points",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Narrative builder
        StructuredOutputContract(
            contract_id="narrative-build/v1",
            task_role=TaskRole.novelty_draft,
            semantic_validator="non_empty_narrative",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Novelty draft generator (D-09)
        StructuredOutputContract(
            contract_id="novelty-draft/v1",
            task_role=TaskRole.novelty_draft,
            semantic_validator="has_novelty_drafts",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Novelty reviewer pressure-test (D-09)
        StructuredOutputContract(
            contract_id="novelty-review/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="validate_novelty_review",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Falsifiability planner (D-09)
        StructuredOutputContract(
            contract_id="falsifiability-batch/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="validate_falsifiability_batch",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
        # Claim judge (D-12)
        StructuredOutputContract(
            contract_id="claim-judge/v1",
            task_role=TaskRole.evidence_critic,
            semantic_validator="validate_claim_judge",
            repair_strategy="fallback_model_once",
            fallback_behavior="typed_failure",
        ),
    ]

    registered = 0
    for c in contracts:
        existing = reg.get_by_id(c.contract_id)
        if existing is None:
            reg.register(c)
            registered += 1
    return registered
