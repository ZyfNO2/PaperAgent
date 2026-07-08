"""LangGraph nodes: dataset/repo extractor + evidence auditor/baseline classifier
+ work package + low-bar review + human gate + final recommendation.

Each node writes trace_events, never mutates state in place, and returns only
the fields it owns (see ResearchState docstring).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Dataset / repo extraction from verified papers (Re1.1 §9 applies)
# ---------------------------------------------------------------------------

def dataset_repo_node(state: ResearchState) -> dict[str, Any]:
    papers = state.get("verified_papers") or []
    t0 = time.time()
    datasets: list[dict[str, Any]] = []
    repos: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    tried = 0

    for p in papers[:8]:  # cap LLM calls so Re1.1 loop stays < 120s
        title = p.get("title") or ""
        if not title:
            continue
        try:
            from apps.api.app.services import llm_router
            from apps.api.app.services.agents.prompts import re11_dataset_repo_extractor as P
            built = P.build(title, p.get("abstract") or p.get("snippet") or "")
            out = llm_router.call_json(
                built["user"], system=built["system"], profile="fast_json",
                max_tokens=700,
                timeout=max(5, _env_int("DATASET_REPO_TIMEOUT_S", 45)),
                expected="dict",
                schema_hint='Top-level object with keys: dataset_name, official_code_url, project_page_url, status',
            )
            tried += 1
            status = out.get("status", "not_found_in_paper")
            if status == "found" or status == "url_missing_nepair":
                if out.get("dataset_name") or out.get("official_code_url"):
                    datasets.append({"from_paper": title, "kind": "dataset",
                                     "name": out.get("dataset_name"),
                                     "url": out.get("official_code_url"),
                                     "status": status,
                                     "missing": out.get("missing") or []})
                if out.get("official_code_url") or out.get("project_page_url"):
                    repos.append({"from_paper": title, "kind": "repo",
                                  "url": out.get("official_code_url") or out.get("project_page_url"),
                                  "mentioned_repo": out.get("paper_mentioned_repo"),
                                  "status": status})
            else:
                datasets.append({"from_paper": title, "status": status})
        except Exception as exc:
            logger.debug("dataset_repo lookup failed for %r: %s", title, type(exc).__name__)
            errors.append({"node": "dataset_repo", "for_paper": title,
                           "error": type(exc).__name__})

    trace = _emit("dataset_repo", t0,
                  {"n_papers": len(papers)}, {"n_dataset": len(datasets), "n_repo": len(repos)},
                  [{"tool": "re11_dataset_repo_extractor.llm", "attempts": tried}],
                  "fast_json", errors,
                  state_keys=["dataset_candidates", "repo_candidates",
                              "trace_events", "errors"])
    return {
        "dataset_candidates": datasets,
        "repo_candidates": repos,
        "trace_events": [trace],
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Evidence auditor + baseline/parallel classifier
# ---------------------------------------------------------------------------

def evidence_auditor_node(state: ResearchState) -> dict[str, Any]:
    papers = state.get("verified_papers") or []
    t0 = time.time()

    baselines: list[dict[str, Any]] = []
    parallels: list[dict[str, Any]] = []
    surveys: list[dict[str, Any]] = []

    for p in papers:
        rel = (p.get("relation_to_topic") or "").lower()
        stype = (p.get("source_type") or "paper").lower()
        title = p.get("title") or p.get("name") or ""
        if stype == "survey" or "survey" in title.lower() or "review" in title.lower():
            if not (rel == "direct" or rel == "baseline"):
                surveys.append(p)
                continue
        if rel == "baseline" or stype == "repo":
            baselines.append(p)
        elif rel == "parallel" or rel == "proxy":
            parallels.append(p)
        else:
            parallels.append(p)  # default to parallel rather than dropping

    trace = _emit("evidence_auditor", t0,
                  {"n_verified": len(papers)},
                  {"n_baseline": len(baselines), "n_parallel": len(parallels),
                   "n_survey": len(surveys)},
                  [{"tool": "re11.classifier", "mode": "rule_based"}],
                  "local", [],
                  state_keys=["baseline_candidates", "parallel_candidates",
                              "evidence_audit", "trace_events"])
    return {
        "baseline_candidates": baselines,
        "parallel_candidates": parallels,
        "evidence_audit": {
            "n_baseline": len(baselines),
            "n_parallel": len(parallels),
            "n_survey": len(surveys),
            "n_total_papers": len(papers),
            "dataset_candidates_n": len(state.get("dataset_candidates") or []),
            "repo_candidates_n": len(state.get("repo_candidates") or []),
        },
        "trace_events": [trace],
    }


# ---------------------------------------------------------------------------
# Work package brainstorm (calls LLM using re11_work_package prompt)
# ---------------------------------------------------------------------------

def work_package_node(state: ResearchState) -> dict[str, Any]:
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    datasets = state.get("dataset_candidates") or []
    repos = state.get("repo_candidates") or []
    constraints = state.get("user_constraints") or {}
    t0 = time.time()
    errors_out: list[dict[str, Any]] = []
    packages: list[dict[str, Any]] = []
    gap: list[dict[str, Any]] = []

    if not (baselines or parallels):
        gap.append({
            "missing": "baseline + parallel paper evidence",
            "tool_calls": [
                {"tool": "search_openalex",
                 "query": f'{atoms.get("method",[["?"]])[-1]} {atoms.get("object",[["?"]])[-1]}',
                 "expected_evidence": "baseline papers"},
            ],
        })
    else:
        try:
            from apps.api.app.services import llm_router
            from apps.api.app.services.agents.prompts import re11_work_package as P
            built = P.build(topic, atoms, baselines=baselines, parallels=parallels,
                            datasets=datasets, repos=repos, constraints=constraints)
            out = llm_router.call_json(
                built["user"], system=built["system"], profile="fast_json",
                max_tokens=1800,
                timeout=max(5, _env_int("WORK_PACKAGE_TIMEOUT_S", 45)),
                expected="dict",
                schema_hint='Top-level object with keys: work_packages (list), evidence_gap (list)',
            )
            packages = out.get("work_packages") or []
            gap = out.get("evidence_gap") or []
            if not isinstance(packages, list):
                packages = []
        except Exception as exc:
            logger.exception("work_package llm call failed")
            errors_out.append({"node": "work_package", "error": type(exc).__name__})
            gap.append({"missing": "llm_unavailable", "tool_calls": []})

    trace = _emit("work_package", t0,
                  {"n_baseline": len(baselines), "n_parallel": len(parallels)},
                  {"n_packages": len(packages), "n_gap": len(gap)},
                  [{"tool": "re11_work_package.llm", "profile": "fast_json"}],
                  "fast_json", errors_out,
                  state_keys=["work_packages", "evidence_audit",
                              "trace_events", "errors"])
    return {
        "work_packages": packages,
        "evidence_audit": {
            **(state.get("evidence_audit") or {}),
            "evidence_gap": gap,
        },
        "trace_events": [trace],
        "errors": errors_out,
    }


# ---------------------------------------------------------------------------
# Low-bar reviewer (rule-based heuristic pass; consults legacy_reviewer when avail)
# ---------------------------------------------------------------------------

def low_bar_review_node(state: ResearchState) -> dict[str, Any]:
    packages = state.get("work_packages") or []
    papers = state.get("verified_papers") or []
    baseline = state.get("baseline_candidates") or []
    parallel = state.get("parallel_candidates") or []
    datasets = state.get("dataset_candidates") or []
    repos = state.get("repo_candidates") or []
    evidence_graph = state.get("evidence_graph") or {}
    t0 = time.time()

    issues: list[str] = []
    if not papers:
        issues.append("no verified papers -- cannot ground a work package")
    if not packages:
        issues.append("no work packages produced; evidence may be insufficient")
    if len(papers) < 3:
        issues.append(f"thin evidence: only {len(papers)} verified paper(s); "
                      "review repair plan")

    # Build the set of evidence-backed sources a work package may cite.
    # Accept ANY entry from verified_papers / baseline / parallel / datasets
    # / repos, plus all node ids appearing in the evidence_graph.
    evidence_titles: set[str] = set()
    for p in papers + baseline + parallel + datasets + repos:
        for key in ("title", "name", "full_name"):
            v = (p.get(key) or "").strip().lower()
            if v:
                evidence_titles.add(v)
    for n in (evidence_graph.get("nodes") or []):
        nid = (n.get("id") or "").strip().lower()
        if nid:
            evidence_titles.add(nid)
        nt = (n.get("title") or "").strip().lower()
        if nt:
            evidence_titles.add(nt)

    # Drop packages whose critical sources do not appear anywhere in the
    # evidence pool.  This blocks hallucinated citations (SOP §15).
    kept: list[dict[str, Any]] = []
    for pkg in packages:
        pkg_baseline = (pkg.get("baseline") or "").strip().lower()
        pkg_source = (pkg.get("improved_module_source") or "").strip().lower()
        pkg_data = (pkg.get("data_source") or "").strip().lower()
        pkg_metrics = (pkg.get("experiment_metrics") or "").strip().lower()

        if pkg_baseline and pkg_baseline not in evidence_titles:
            issues.append(
                f"work-package baseline not in evidence graph: {pkg.get('baseline')}")
            continue
        if pkg_source and pkg_source not in evidence_titles:
            issues.append(
                f"work-package module source not in evidence graph: "
                f"{pkg.get('improved_module_source')}")
            continue
        # data_source / metrics are softer; only warn, do not drop.
        if pkg_data and pkg_data not in evidence_titles:
            issues.append(
                f"work-package data_source not in evidence graph (weak): "
                f"{pkg.get('data_source')}")
        if pkg_metrics and pkg_metrics not in evidence_titles:
            issues.append(
                f"work-package metrics source not in evidence graph (weak): "
                f"{pkg.get('experiment_metrics')}")
        kept.append(pkg)

    review = {"status": "pass" if not issues else "blocked",
              "issues": issues, "n_packages_reviewed": len(packages),
              "n_packages_after_review": len(kept)}

    trace = _emit("low_bar_review", t0,
                  {"n_packages": len(packages)},
                  {"status": review["status"], "n_remaining": len(kept)},
                  [{"tool": "low_bar.rule_based"}],
                  "local", [],
                  state_keys=["low_bar_review", "work_packages", "trace_events"])
    return {"low_bar_review": review,
            "work_packages": kept,
            "trace_events": [trace]}


# ---------------------------------------------------------------------------
# Human gate — pass-through unless HUMAN_GATE_ENABLED=true (Re1.1 §6)
# ---------------------------------------------------------------------------

def human_gate_node(state: ResearchState) -> dict[str, Any]:
    import os
    enabled = os.environ.get("HUMAN_GATE_ENABLED", "false").lower() == "true"
    t0 = time.time()
    if enabled:
        from langgraph.types import interrupt
        try:
            decision = interrupt({
                "kind": "human_gate",
                "n_papers": len(state.get("verified_papers") or []),
                "n_packages": len(state.get("work_packages") or []),
            })
            gate = {"status": "interrupted", "decision": decision}
        except RuntimeError:
            # Running offline / not resumable: treat as not-enabled.
            gate = {"status": "pass_through_no_runtime", "reason": "no checkpointer"}
    else:
        gate = {"status": "pass_through", "reason": "HUMAN_GATE_ENABLED!=true"}

    trace = _emit("human_gate", t0, {"enabled": enabled},
                  {"status": gate["status"]}, [],
                  "local", [],
                  state_keys=["human_gate", "trace_events"])
    return {"human_gate": gate,
            "trace_events": [trace]}


# ---------------------------------------------------------------------------
# Final recommendation — summarize evidence + work package + audit
# ---------------------------------------------------------------------------

def final_recommendation_node(state: ResearchState) -> dict[str, Any]:
    review = state.get("low_bar_review") or {}
    packages = state.get("work_packages") or []
    gate = state.get("human_gate") or {}
    t0 = time.time()

    notes: list[str] = []
    if review.get("status") == "blocked":
        notes.append("low-bar review blocked the proposal")
    if gate.get("status") not in ("pass_through", "pass_through_no_runtime"):
        notes.append(f"human gate: {gate.get('status')}")

    recommendation = {
        "topic": state.get("topic"),
        "n_papers": len(state.get("verified_papers") or []),
        "n_baseline": len(state.get("baseline_candidates") or []),
        "n_parallel": len(state.get("parallel_candidates") or []),
        "n_dataset": len(state.get("dataset_candidates") or []),
        "n_repo": len(state.get("repo_candidates") or []),
        "n_work_packages": len(packages),
        "low_bar_status": review.get("status"),
        "human_gate_status": gate.get("status"),
        "notes": notes,
        "research_basis": packages,
    }
    trace = _emit("final_recommendation", t0, {}, recommendation,
                  [], "local", [],
                  state_keys=["final_recommendation", "trace_events"])
    return {"final_recommendation": recommendation,
            "trace_events": [trace]}
