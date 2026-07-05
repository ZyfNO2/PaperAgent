"""Graph node package — flat registry of all Re1.3 LangGraph nodes.

Each module exposes a `<name>_node(state: ResearchState) -> dict[str, Any]`
patch function.

Re1.3 adds: quality_filter, citation_expander
"""
from __future__ import annotations

from . import baseline_classifier as _baseline_classifier
from . import citation_expander as _citation_expander
from . import content as _content
from . import dataset_repo_extractor as _dataset_repo_extractor
from . import intake as _intake
from . import json_graph_builder as _json_graph_builder
from . import quality_filter as _quality_filter
from . import quality_gate as _quality_gate
from . import retrieve as _retrieve
from . import search_planner as _search_planner
from . import targeted_repair as _targeted_repair
from . import topic_parser as _topic_parser
from . import verify as _verify
# Re1.4 analysis nodes
from . import feasibility_assessor as _feasibility
from . import innovation_extractor as _innovation
from . import sota_matcher as _sota
from . import narrative_builder as _narrative
from . import optimization_advisor as _optimization
from . import devils_advocate_node as _devils

# Every node is a (ResearchState) -> dict[str, Any] patch function.
REGISTRY: dict[str, callable] = {
    "intake": _intake.intake_node,
    "topic_parser": _topic_parser.topic_parser_node,
    "search_planner": _search_planner.search_planner_node,
    "paper_retriever": _retrieve.retrieve_node,
    "retrieve": _retrieve.retrieve_node,                    # Re1.1 compat alias
    "quality_filter": _quality_filter.quality_filter_node,  # Re1.3
    "paper_verifier": _verify.verify_node,
    "verify": _verify.verify_node,                          # Re1.1 compat alias
    "citation_expander": _citation_expander.citation_expander_node,  # Re1.3
    "dataset_repo_extractor": _dataset_repo_extractor.dataset_repo_extractor_node,
    "dataset_repo": _dataset_repo_extractor.dataset_repo_extractor_node,  # Re1.1 compat
    "quality_gate": _quality_gate.quality_gate_node,
    "targeted_repair": _targeted_repair.targeted_repair_node,
    "evidence_graph_builder": _json_graph_builder.json_graph_builder_node,
    "baseline_classifier": _baseline_classifier.baseline_classifier_node,
    "evidence_auditor": _baseline_classifier.baseline_classifier_node,  # Re1.1 compat
    "work_package_brainstorm": _content.work_package_node,
    "work_package": _content.work_package_node,             # Re1.1 compat alias
    "low_bar_review": _content.low_bar_review_node,
    "human_gate": _content.human_gate_node,
    "final_recommendation": _content.final_recommendation_node,
    # Re1.4 analysis nodes
    "feasibility_assessor": _feasibility.feasibility_assessor_node,
    "innovation_extractor": _innovation.innovation_extractor_node,
    "sota_matcher": _sota.sota_matcher_node,
    "narrative_builder": _narrative.narrative_builder_node,
    "optimization_advisor": _optimization.optimization_advisor_node,
    "devils_advocate": _devils.devils_advocate_node,
}

NODE_FIELDS: dict[str, tuple[str, ...]] = {
    "intake": ("case_id", "trace_events", "errors", "provider_profile"),
    "topic_parser": ("topic_atoms", "trace_events", "errors", "provider_profile"),
    "search_planner": ("search_plan", "trace_events", "errors", "provider_profile"),
    "paper_retriever": ("raw_results", "paper_candidates", "trace_events",
                       "errors", "provider_profile"),
    "quality_filter": ("paper_candidates", "filter_results", "trace_events", "errors"),
    "paper_verifier": ("verified_papers", "paper_candidates", "trace_events",
                      "errors", "provider_profile"),
    "citation_expander": ("seed_papers", "expanded_papers", "surveys_found",
                         "repos_found", "citation_expansion_done", "paper_candidates",
                         "trace_events", "errors"),
    "quality_gate": ("evidence_audit", "trace_events"),
    "targeted_repair": ("search_plan", "evidence_audit", "trace_events", "errors"),
    "dataset_repo_extractor": ("dataset_candidates", "repo_candidates",
                              "evidence_audit", "trace_events", "errors"),
    "evidence_graph_builder": ("evidence_graph", "evidence_audit", "trace_events"),
    "baseline_classifier": ("baseline_candidates", "parallel_candidates",
                           "dataset_papers", "surveys", "evidence_audit",
                           "trace_events"),
    "work_package_brainstorm": ("work_packages", "evidence_audit",
                                "trace_events", "errors"),
    "low_bar_review": ("low_bar_review", "work_packages", "trace_events"),
    "human_gate": ("human_gate", "trace_events"),
    "final_recommendation": ("final_recommendation", "trace_events"),
    # Re1.4 analysis nodes
    "feasibility_assessor": ("feasibility_report", "trace_events"),
    "innovation_extractor": ("innovation_points", "stitching_plan", "trace_events"),
    "sota_matcher": ("sota_comparison", "trace_events"),
    "narrative_builder": ("research_narratives", "trace_events"),
    "optimization_advisor": ("optimization_directions", "trace_events"),
    "devils_advocate": ("review_report", "trace_events"),
}
