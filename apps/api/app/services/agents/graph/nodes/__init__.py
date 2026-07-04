"""Graph node package — each module owns one or more ResearchState fields.

Expose a flat registry so the graph builder can reference nodes by string name.
"""
from __future__ import annotations

from . import content as _content
from . import retrieve as _retrieve
from . import verify as _verify

# Every node is a (ResearchState) -> dict[str, Any] patch function.
REGISTRY: dict[str, callable] = {
    "retrieve": _retrieve.retrieve_node,
    "verify": _verify.verify_node,
    "dataset_repo": _content.dataset_repo_node,
    "evidence_auditor": _content.evidence_auditor_node,
    "work_package": _content.work_package_node,
    "low_bar_review": _content.low_bar_review_node,
    "human_gate": _content.human_gate_node,
    "final_recommendation": _content.final_recommendation_node,
}

NODE_FIELDS: dict[str, tuple[str, ...]] = {
    "retrieve": ("raw_results", "paper_candidates", "trace_events",
                "errors", "provider_profile"),
    "verify": ("verified_papers", "paper_candidates", "trace_events",
               "errors", "provider_profile"),
    "dataset_repo": ("dataset_candidates", "repo_candidates", "trace_events",
                    "errors"),
    "evidence_auditor": ("baseline_candidates", "parallel_candidates",
                        "evidence_audit", "trace_events"),
    "work_package": ("work_packages", "evidence_audit", "trace_events",
                    "errors"),
    "low_bar_review": ("low_bar_review", "work_packages", "trace_events"),
    "human_gate": ("human_gate", "trace_events"),
    "final_recommendation": ("final_recommendation", "trace_events"),
}
