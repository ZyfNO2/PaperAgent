"""LangGraph nodes: dataset/repo extractor + evidence auditor/baseline classifier
+ work package + low-bar review + human gate + final recommendation.

Each node writes trace_events, never mutates state in place, and returns only
the fields it owns (see ResearchState docstring).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.graph.nodes.reflection_gates import (
    GATE_FINAL_REVIEW,
    GATE_SEED_AUDIT,
    GATE_TAILOR,
)
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
    prov = "local"

    for p in papers[:8]:  # cap LLM calls so Re1.1 loop stays < 120s
        title = p.get("title") or ""
        if not title:
            continue
        try:
            from apps.api.app.services.agents.prompts import re11_dataset_repo_extractor as P
            from ._unified_migrate import call_structured
            from apps.api.app.services.router.model_policy import TaskRole
            built = P.build(title, p.get("abstract") or p.get("snippet") or "")
            out, _prov = call_structured(
                prompt=built["user"], system=built["system"],
                task_role=TaskRole.structured_extract, contract_id="dataset-repo-extraction/v1",
                env_flag="CONTENT_DATASET_REPO_USE_UNIFIED",
                fallback_fn=lambda: {"status": "not_found_in_paper"},
                validator_name="",
                max_tokens=700, timeout=max(5, _env_int("DATASET_REPO_TIMEOUT_S", 45)),
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
                  [{"tool": "dataset-repo-extraction/v1" if prov == "unified_router" else "re11_dataset_repo_extractor.llm",
                    "attempts": tried, "mode": prov}],
                  prov, errors,
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
        from apps.api.app.services.agents.prompts import re11_work_package as P
        from ._unified_migrate import call_structured
        from apps.api.app.services.router.model_policy import TaskRole
        built = P.build(topic, atoms, baselines=baselines, parallels=parallels,
                        datasets=datasets, repos=repos, constraints=constraints)
        out, _prov = call_structured(
            prompt=built["user"], system=built["system"],
            task_role=TaskRole.evidence_critic, contract_id="work-package/v1",
            env_flag="WORK_PACKAGE_USE_UNIFIED",
            fallback_fn=lambda: {"work_packages": [], "evidence_gap": [{"missing": "llm_unavailable", "tool_calls": []}]},
            validator_name="has_work_packages",
            max_tokens=1800, timeout=max(5, _env_int("WORK_PACKAGE_TIMEOUT_S", 45)),
            expected="dict",
            schema_hint='Top-level object with keys: work_packages (list), evidence_gap (list)',
        )
        packages = out.get("work_packages") or []
        gap = out.get("evidence_gap") or []
        if not isinstance(packages, list):
            packages = []
        if not gap:
            gap.append({"missing": "", "tool_calls": []})
        if _prov == "heuristic":
            errors_out.append({"node": "work_package", "error": "llm_unavailable"})

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
    # Re8.0 post-audit: work_package fields may be lists (not just str),
    # so coerce to str before .strip(). Previous code crashed with
    # AttributeError when data_source was a list.
    def _pkg_str(pkg: dict[str, Any], key: str) -> str:
        val = pkg.get(key)
        if isinstance(val, list):
            return " ".join(str(x) for x in val).strip().lower()
        return (str(val) if val else "").strip().lower()

    kept: list[dict[str, Any]] = []
    for pkg in packages:
        pkg_baseline = _pkg_str(pkg, "baseline")
        pkg_source = _pkg_str(pkg, "improved_module_source")
        pkg_data = _pkg_str(pkg, "data_source")
        pkg_metrics = _pkg_str(pkg, "experiment_metrics")

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

    # Re4.3: Binding validation + DAG
    try:
        from apps.api.app.services.agents.graph.validators.binding_validator import run_full_validation
        from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag
        binding_result = run_full_validation(state)
        if not binding_result.valid:
            issues.extend([f"binding: {i['message']}" for i in binding_result.issues])
        review["binding_validation"] = binding_result.model_dump()

        dag = build_dag(kept)
        review["dag"] = dag
        if dag["has_cycle"]:
            issues.append("work package dependency cycle detected")
    except Exception:
        pass

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


def human_gate_search_node(state: ResearchState) -> dict[str, Any]:
    """Re3.9.3: Human gate after search+verify, before analysis.

    Pauses execution to let user review search results.
    In debug mode (HUMAN_GATE_ENABLED=false), passes through automatically.
    """
    import os
    enabled = os.environ.get("HUMAN_GATE_ENABLED", "false").lower() == "true"
    t0 = time.time()

    vp = state.get("verified_papers") or []
    feas = state.get("feasibility_report") or {}

    if enabled:
        from langgraph.types import interrupt
        try:
            decision = interrupt({
                "kind": "human_gate_search",
                "message": "搜索阶段完成，请确认是否继续分析",
                "n_verified": len(vp),
                "n_repos": len(state.get("repo_candidates") or []),
                "n_datasets": len(state.get("dataset_candidates") or []),
                "feasibility_verdict": feas.get("verdict", ""),
                "feasibility_score": feas.get("score", 0),
            })
            gate = {"status": "confirmed", "decision": decision}
        except RuntimeError:
            gate = {"status": "pass_through_no_runtime", "reason": "no checkpointer"}
    else:
        gate = {"status": "pass_through", "reason": "debug mode (HUMAN_GATE_ENABLED!=true)"}

    trace = _emit("human_gate_search", t0,
                  {"enabled": enabled, "n_papers": len(vp)},
                  {"status": gate["status"]}, [],
                  "local", [],
                  state_keys=["human_gate_search", "trace_events"])
    return {"human_gate_search": gate, "trace_events": [trace]}


# ---------------------------------------------------------------------------
# Final recommendation — summarize evidence + work package + audit
# ---------------------------------------------------------------------------

def _domain_risk_level(state: ResearchState) -> str:
    """Classify domain risk as high/medium/low based on topic + domain.

    Re7.7 round-5: introduced to let _compute_final_verdict factor domain
    risk into the verdict mapping independently of claim_judge's prompt-level
    Domain risk check. This corrects cases where claim_judge returns REJECT
    for a high-risk domain but low_bar passes (should still STOP), and cases
    where low_bar blocks + REJECT on a low-risk domain (should be RISKY, not STOP).
    """
    constraints = state.get("user_constraints") or {}
    domain = str(constraints.get("domain", "")).lower()
    topic = str(state.get("topic", "")).lower()
    text = f"{domain} {topic}"

    high_risk_kws = [
        "罕见病", "药物反应", "心理咨询", "精神", "malicious", "钓鱼",
        "phishing", "deepfake", "fraud", "恶意", "mental health",
    ]
    medium_risk_kws = [
        "医学", "医疗", "临床", "clinical", "自动驾驶", "autonomous",
        "金融风控", "financial", "医学影像", "medical",
    ]

    for kw in high_risk_kws:
        if kw.lower() in text:
            return "high"
    for kw in medium_risk_kws:
        if kw.lower() in text:
            return "medium"
    return "low"


def _compute_final_verdict(state: ResearchState) -> str:
    """Compute GO / CONDITIONAL / RISKY / PIVOT / STOP verdict from available node outputs.

    Re7.7 round-6 calibration:
      - REMOVED medium-risk+REJECT+blocked→STOP (was too aggressive; XD-04 expects RISKY)
      - ADDED high-risk+ACCEPT→CONDITIONAL (high-risk domains never get a clean GO;
        XD-09 rare-disease drug response must not be GO even if claim_judge ACCEPTs)
      - medium-risk now behaves like low-risk for REJECT (→ RISKY, not STOP)
    """
    review = state.get("low_bar_review") or {}
    gate = state.get("human_gate") or {}
    claim_judge_verdict = (state.get("claim_judge_verdict") or "").upper()
    blocked_items = state.get("blocked_items") or []
    devils = state.get("devils_advocate") or {}

    low_bar_blocked = review.get("status") == "blocked"
    is_reject = claim_judge_verdict == "REJECT"
    is_revise = claim_judge_verdict == "REVISE"
    is_accept = claim_judge_verdict == "ACCEPT"
    risk = _domain_risk_level(state)

    # 1. human gate not passed → STOP
    gate_status = gate.get("status", "")
    if gate_status not in ("pass_through", "pass_through_no_runtime"):
        return "STOP"
    # 2. high-risk domain + REJECT → STOP (even if low_bar pass)
    if risk == "high" and is_reject:
        return "STOP"
    # 3. high-risk domain + REVISE + low_bar blocked → STOP
    if risk == "high" and is_revise and low_bar_blocked:
        return "STOP"
    # 4. revise + fundamental flaw → PIVOT
    if is_revise and devils.get("fundamental_flaw"):
        return "PIVOT"
    # 5. REJECT alone → RISKY (not STOP; claim judge may be overly strict)
    if is_reject:
        return "RISKY"
    # 6. judge unavailable → RISKY (not STOP)
    if claim_judge_verdict == "UNAVAILABLE":
        return "RISKY"
    # 7. low_bar blocked + REJECT/REVISE → RISKY (not STOP in low/medium-risk domains)
    if low_bar_blocked and (is_reject or is_revise):
        return "RISKY"
    # 8. low_bar blocked + ACCEPT → CONDITIONAL (can proceed with caveats)
    if low_bar_blocked and is_accept:
        return "CONDITIONAL"
    # 9. low_bar blocked with unknown claim judge → RISKY
    if low_bar_blocked:
        return "RISKY"
    # 10. REVISE + low_bar pass → CONDITIONAL
    if is_revise:
        return "CONDITIONAL"
    # 11. ACCEPT + blocked items → CONDITIONAL
    if is_accept and blocked_items:
        return "CONDITIONAL"
    # 12. blocked items → RISKY
    if blocked_items:
        return "RISKY"
    # 13. high-risk domain + ACCEPT → CONDITIONAL (never clean GO for high-risk)
    if risk == "high" and is_accept:
        return "CONDITIONAL"
    # 14. all clear → GO
    return "GO"


def _compute_stop_reason(state: ResearchState) -> list[str]:
    """Return human-readable reasons for STOP / RISKY / CONDITIONAL / PIVOT verdicts."""
    reasons: list[str] = []
    review = state.get("low_bar_review") or {}
    gate = state.get("human_gate") or {}
    claim_judge_verdict = (state.get("claim_judge_verdict") or "").upper()
    blocked_items = state.get("blocked_items") or []
    verdict = _compute_final_verdict(state)

    if review.get("status") == "blocked":
        reasons.append("low-bar review blocked the proposal")
    if claim_judge_verdict == "REJECT":
        reasons.append("claim judge rejected all novelty claims")
    if claim_judge_verdict == "UNAVAILABLE":
        reasons.append("claim judge unavailable, cannot assess novelty")
    gate_status = gate.get("status", "")
    if gate_status not in ("pass_through", "pass_through_no_runtime"):
        reasons.append(f"human gate did not pass: {gate_status}")
    if claim_judge_verdict == "REVISE":
        reasons.append("claim judge requested revisions")
    if blocked_items:
        reasons.append(f"{len(blocked_items)} claim(s) blocked")
    if verdict == "CONDITIONAL":
        if blocked_items:
            reasons.append(f"{len(blocked_items)} claim(s) blocked but core claims accepted")
        elif _domain_risk_level(state) == "high":
            reasons.append("high-risk domain requires conditional review (never clean GO)")
        # else: REVISE already added its own reason above
    if verdict == "PIVOT":
        reasons.append("fundamental flaw identified by devils_advocate, pivot recommended")

    return reasons[:3]


# ---------------------------------------------------------------------------
# Re8.0 P1-2: Decision Fusion — combine 3 Reflection Gate verdicts + novelty
# review + critical evidence gaps into a single fused_verdict. This is a PURE
# function (no side effects): takes state, returns (verdict, rationale).
# ---------------------------------------------------------------------------

# Critical gap types — gaps of these types block a clean GO when their status
# is "open" (Plan §8.7 / Re8.0 P1-2). repo / environment / counter_evidence /
# existence gaps are important but not load-bearing for the core claim, so
# they do NOT block GO on their own.
_CRITICAL_GAP_TYPES = frozenset({
    "current_baseline",
    "competing_method",
    "dataset",
    "mechanism",
})


def _gate_verdict(state: dict, gate_name: str) -> str:
    """Return the last verdict emitted by ``gate_name``.

    A gate with no entries (wasn't run, e.g. Lite Chain / Offline Replay
    short-circuit) is treated as ``"pass"`` — missing gates do not block
    (Re8.0 P1-2). A malformed verdict is also treated as ``"pass"`` so a
    noisy gate result never silently hard-stops the pipeline.
    """
    results = (state.get("reflection_gate_results") or {}).get(gate_name, [])
    if not results:
        return "pass"
    last = results[-1]
    if not isinstance(last, dict):
        return "pass"
    verdict = str(last.get("verdict") or "").strip().lower()
    if verdict not in ("pass", "revise", "unresolved"):
        return "pass"
    return verdict


def _has_open_critical_gap(state: dict) -> bool:
    """True iff any evidence gap with a critical gap_type has status='open'."""
    for gap in (state.get("evidence_gaps") or []):
        if not isinstance(gap, dict):
            continue
        if gap.get("gap_type") in _CRITICAL_GAP_TYPES and gap.get("status") == "open":
            return True
    return False


def _compute_fused_verdict(state: dict) -> tuple[str, str]:
    """Compute fused verdict from all upstream signals.

    Returns (fused_verdict, rationale).

    fused_verdict is one of: "GO", "CONDITIONAL", "RISKY", "BLOCKED"

    Rules (evaluated in order, first match wins):
    1. Seed Audit gate verdict="unresolved" → ("BLOCKED", "seed audit unresolved")
    2. Tailor gate verdict="unresolved" → ("BLOCKED", "tailor unresolved")
    3. Final Review gate verdict="unresolved" → ("BLOCKED", "final review unresolved")
    4. Novelty review verdict="reject" AND tailor verdict="GO" → ("RISKY", "novelty rejected but engineering viable")
    5. Any gate verdict="revise" → ("CONDITIONAL", "gates requested revision")
    6. Any critical evidence gap with status="open" → ("CONDITIONAL", "critical gaps open")
    7. All gates="pass" + novelty="accepted" + no open critical gaps → ("GO", "all checks passed")
    8. Default → ("CONDITIONAL", "insufficient signals for GO")

    Sources:
      - Gate verdicts: state["reflection_gate_results"][gate_name][-1]["verdict"]
        (last entry wins; missing gate → "pass").
      - Novelty: state["novelty_review_verdict"] ∈ {"accepted","weak_reject","reject"}.
      - Tailor skill verdict: state["tailored_method"]["verdict"] ∈
        {"GO","NO-GO","CONDITIONAL",""}.
      - Gaps: state["evidence_gaps"][*]["gap_type"] / ["status"].
    """
    seed_audit = _gate_verdict(state, GATE_SEED_AUDIT)
    tailor_gate = _gate_verdict(state, GATE_TAILOR)
    final_review = _gate_verdict(state, GATE_FINAL_REVIEW)

    novelty = str(state.get("novelty_review_verdict") or "").strip().lower()
    tailor_verdict = str(
        (state.get("tailored_method") or {}).get("verdict", "")
    ).strip().upper()

    # Rules 1-3: unresolved gate → BLOCKED (hard stop, in declaration order).
    if seed_audit == "unresolved":
        return ("BLOCKED", "seed audit unresolved")
    if tailor_gate == "unresolved":
        return ("BLOCKED", "tailor unresolved")
    if final_review == "unresolved":
        return ("BLOCKED", "final review unresolved")

    # Rule 4: novelty rejected but engineering method viable → RISKY.
    if novelty == "reject" and tailor_verdict == "GO":
        return ("RISKY", "novelty rejected but engineering viable")

    # Rule 5: any gate requested revision → cap at CONDITIONAL (not GO).
    if "revise" in (seed_audit, tailor_gate, final_review):
        return ("CONDITIONAL", "gates requested revision")

    # Rule 6: open critical evidence gap → cannot be GO.
    if _has_open_critical_gap(state):
        return ("CONDITIONAL", "critical gaps open")

    # Rule 7: all clear → GO. (Gates are guaranteed "pass" here since
    # revise/unresolved were handled above; the explicit check is kept for
    # clarity and to defend against future rule reordering.)
    if (
        seed_audit == "pass"
        and tailor_gate == "pass"
        and final_review == "pass"
        and novelty == "accepted"
        and not _has_open_critical_gap(state)
    ):
        return ("GO", "all checks passed")

    # Rule 8: insufficient positive signals for a clean GO.
    return ("CONDITIONAL", "insufficient signals for GO")


# ---------------------------------------------------------------------------
# Re8.0 P1-3: Final Research Package — assemble a single auditable object
# that carries the 7 sections required by spec §"Final Research Package":
#   1. seed_audit_summary   — key fields from each SeedPaperCard
#   2. tailor_summary       — key fields from tailored_method + contribution_type
#   3. gate_results         — LAST verdict of each of the 3 Reflection Gates
#   4. ledger_entries       — key fields from each ReasoningLedgerEntry
#   5. evidence_gap_status  — counts by status + list of open gap summaries
#   6. falsifiable_hypothesis — hypothesis string (or "unspecified")
#   7. fused_verdict        — verdict + rationale from _compute_fused_verdict
#
# This is a PURE function: takes a state dict, returns a package dict. It
# never raises on missing/empty source data — every section degrades to an
# empty list / dict / "unspecified" instead. All values are JSON-serializable
# (str/int/float/bool/list/dict/None); non-serializable values are str()-cast.
# ---------------------------------------------------------------------------

# Section field names (single source of truth — kept in sync with spec).
_GATE_RESULT_FIELDS = ("verdict", "round_idx", "rationale", "re_search_requests")
_LEDGER_FIELDS = ("decision_id", "stage", "decision", "status", "confidence")
_SEED_AUDIT_FIELDS = ("seed_id", "resolved_title", "existence_status", "role", "fulltext_status")
_GAP_STATUS_BUCKETS = ("open", "satisfied", "partially_satisfied", "blocked")


def _safe_str(value: Any) -> str:
    """Coerce any value to a JSON-safe string (None → '')."""
    if value is None:
        return ""
    return str(value)


def _assemble_final_research_package(state: dict) -> dict:
    """Assemble the Final Research Package from all pipeline stages.

    Returns a dict with 7 sections:
    1. seed_audit_summary: seed_cards with key fields (seed_id, resolved_title, existence_status, role, fulltext_status)
    2. tailor_summary: tailored_method with key fields (verdict, core_method, baseline_model, ablation_matrix count, contribution_type)
    3. gate_results: dict mapping each of 3 gate names to its last verdict/round_idx/rationale/re_search_requests
    4. ledger_entries: list of reasoning_ledger entries (decision_id, stage, decision, status, confidence)
    5. evidence_gap_status: dict with counts by status (open/satisfied/partially_satisfied/blocked) + list of open gap summaries
    6. falsifiable_hypothesis: the hypothesis string (or "unspecified" if missing)
    7. fused_verdict: the fused_verdict and its rationale (from _compute_fused_verdict)

    Pure function: no side effects, no I/O, never raises on missing data.
    All returned values are JSON-serializable.
    """
    # ── 1. seed_audit_summary ─────────────────────────────────────────────
    seed_cards = state.get("seed_cards") or []
    if not isinstance(seed_cards, list):
        seed_cards = []
    seed_audit_summary: list[dict[str, Any]] = []
    for card in seed_cards:
        if not isinstance(card, dict):
            continue
        seed_audit_summary.append({
            "seed_id": _safe_str(card.get("seed_id")),
            "resolved_title": _safe_str(card.get("resolved_title")),
            "existence_status": _safe_str(card.get("existence_status") or "ambiguous"),
            "role": _safe_str(card.get("role") or "unknown"),
            "fulltext_status": _safe_str(card.get("fulltext_status") or "metadata_only"),
        })

    # ── 2. tailor_summary ─────────────────────────────────────────────────
    tailored = state.get("tailored_method") or {}
    if not isinstance(tailored, dict):
        tailored = {}
    primary_baseline = tailored.get("primary_baseline") or {}
    if not isinstance(primary_baseline, dict):
        primary_baseline = {}
    assembly_plan = tailored.get("assembly_plan") or {}
    if not isinstance(assembly_plan, dict):
        assembly_plan = {}
    ablation_matrix = tailored.get("ablation_matrix") or []
    if not isinstance(ablation_matrix, list):
        ablation_matrix = []
    # core_method derivation: prefer explicit field (test fixtures), fall
    # back to assembly_plan.description (production schema from tailor_skill_adapter).
    core_method = tailored.get("core_method")
    if core_method is None:
        core_method = assembly_plan.get("description", "")
    tailor_summary: dict[str, Any] = {
        "verdict": _safe_str(tailored.get("verdict")),
        "core_method": _safe_str(core_method),
        "baseline_model": _safe_str(primary_baseline.get("title")),
        "ablation_matrix_count": len(ablation_matrix),
        "contribution_type": _safe_str(state.get("contribution_type") or "unknown"),
    }

    # ── 3. gate_results (LAST entry of each gate) ─────────────────────────
    gate_results_raw = state.get("reflection_gate_results") or {}
    if not isinstance(gate_results_raw, dict):
        gate_results_raw = {}
    gate_results: dict[str, dict[str, Any]] = {}
    for gate_name in (GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW):
        entries = gate_results_raw.get(gate_name) or []
        if isinstance(entries, list) and entries:
            last = entries[-1]
            if not isinstance(last, dict):
                last = {}
            try:
                round_idx = int(last.get("round_idx") or 0)
            except (TypeError, ValueError):
                round_idx = 0
            re_search = last.get("re_search_requests") or []
            if not isinstance(re_search, list):
                re_search = []
            gate_results[gate_name] = {
                "verdict": _safe_str(last.get("verdict")),
                "round_idx": round_idx,
                "rationale": _safe_str(last.get("rationale")),
                "re_search_requests": [_safe_str(r) for r in re_search],
            }
        else:
            gate_results[gate_name] = {
                "verdict": "",
                "round_idx": 0,
                "rationale": "",
                "re_search_requests": [],
            }

    # ── 4. ledger_entries ─────────────────────────────────────────────────
    ledger = state.get("reasoning_ledger") or []
    if not isinstance(ledger, list):
        ledger = []
    ledger_entries: list[dict[str, Any]] = []
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        try:
            confidence = float(entry.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        ledger_entries.append({
            "decision_id": _safe_str(entry.get("decision_id")),
            "stage": _safe_str(entry.get("stage")),
            "decision": _safe_str(entry.get("decision")),
            "status": _safe_str(entry.get("status") or "proposed"),
            "confidence": confidence,
        })

    # ── 5. evidence_gap_status ────────────────────────────────────────────
    gaps = state.get("evidence_gaps") or []
    if not isinstance(gaps, list):
        gaps = []
    counts: dict[str, int] = {s: 0 for s in _GAP_STATUS_BUCKETS}
    open_gaps: list[dict[str, Any]] = []
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        status = _safe_str(gap.get("status") or "open")
        if status in counts:
            counts[status] += 1
        else:
            # Unknown status — bucket under "open" conservatively so the
            # total still adds up; never silently drop a gap.
            counts["open"] += 1
        if status == "open":
            open_gaps.append({
                "gap_id": _safe_str(gap.get("gap_id")),
                "question": _safe_str(gap.get("question")),
                "gap_type": _safe_str(gap.get("gap_type") or "existence"),
            })
    evidence_gap_status: dict[str, Any] = {
        "counts": counts,
        "open_gaps": open_gaps,
    }

    # ── 6. falsifiable_hypothesis ─────────────────────────────────────────
    hypothesis = state.get("falsifiable_hypothesis")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        falsifiable_hypothesis = "unspecified"
    else:
        falsifiable_hypothesis = hypothesis

    # ── 7. fused_verdict ──────────────────────────────────────────────────
    fused_verdict, fused_rationale = _compute_fused_verdict(state)
    fused_verdict_section: dict[str, Any] = {
        "verdict": _safe_str(fused_verdict),
        "rationale": _safe_str(fused_rationale),
    }

    return {
        "seed_audit_summary": seed_audit_summary,
        "tailor_summary": tailor_summary,
        "gate_results": gate_results,
        "ledger_entries": ledger_entries,
        "evidence_gap_status": evidence_gap_status,
        "falsifiable_hypothesis": falsifiable_hypothesis,
        "fused_verdict": fused_verdict_section,
    }


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

    verdict = _compute_final_verdict(state)
    stop_reason = _compute_stop_reason(state)
    fused_verdict, fused_rationale = _compute_fused_verdict(state)
    # Re8.0 P1-3: assemble the Final Research Package (7 sections) from all
    # upstream stages. Pure call — degrades to empty/default sections when
    # source data is missing.
    research_package = _assemble_final_research_package(state)
    artifact_id = f"rec-{uuid.uuid4().hex[:12]}"

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
        "claim_judge_verdict": state.get("claim_judge_verdict"),
        "verdict": verdict,
        "stop_reason": stop_reason,
        "notes": notes,
        "research_basis": packages,
        "artifact_id": artifact_id,
        # Re8.0 P1-2: fused verdict from 3 Reflection Gates + novelty +
        # critical evidence gaps. Kept alongside the legacy verdict so
        # downstream consumers can migrate incrementally.
        "fused_verdict": fused_verdict,
        "fused_verdict_rationale": fused_rationale,
        # Re8.0 P1-3: full research package (7 sections) for downstream
        # consumers / WP7 frontend export. Same object is also written to
        # the top-level ``final_research_package`` state field.
        "research_package": research_package,
    }

    try:
        from apps.api.app.services.feedback_bar import make_feedback_bar_for_final_recommendation
        recommendation["feedback_bar"] = make_feedback_bar_for_final_recommendation(
            state.get("case_id") or "", recommendation
        )
    except Exception:
        import hashlib
        raw = f"{state.get('case_id') or ''}:final_recommendation:{artifact_id}"
        recommendation["feedback_bar"] = {
            "artifact_type": "final_recommendation",
            "artifact_id": artifact_id,
            "idempotency_key": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24],
            "options": ["useful", "incorrect", "unsupported", "needs_more_evidence"],
        }

    trace = _emit("final_recommendation", t0, {}, recommendation,
                  [], "local", [],
                  state_keys=["final_recommendation", "final_research_package",
                              "fused_verdict", "fused_verdict_rationale",
                              "trace_events"])
    # Re8.0 P0-A fixup: also surface fused_verdict at the state top level
    # (not just nested inside final_recommendation). Several diagnostic
    # scripts and the Three-Tier PASS checker read state["fused_verdict"]
    # directly; without this they see null even when final_rec carries the
    # correct value.
    return {"final_recommendation": recommendation,
            "final_research_package": research_package,
            "fused_verdict": fused_verdict,
            "fused_verdict_rationale": fused_rationale,
            "stop_reason": stop_reason,
            "trace_events": [trace]}
