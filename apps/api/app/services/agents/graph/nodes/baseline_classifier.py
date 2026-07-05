"""LangGraph node: evidence_auditor — classify verified papers.

Replaces content.evidence_auditor_node (agent C wires it in). Signature
`baseline_classifier_node(state) -> dict` so a registry change picks it up.

For each verified paper set:
  role / why_relevant / matched_topic_axes / unmatched_topic_axes / next_use
and bucket into baseline_candidates / parallel_candidates / dataset_papers /
surveys / noise. Sets evidence_audit counts.

SOP §5.9: survey/review/systematic titles are NOT baseline even if direct.
No fake-baseline injection when verified_papers is empty.

Output fields: baseline_candidates, parallel_candidates, dataset_papers,
surveys, evidence_audit, trace_events.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _emit(node: str, t0: float, ins: dict, out: dict,
          tools: list, prov: str, errs: list) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": _now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": _now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
    }


def _word_list(d: dict[str, Any], key: str) -> list[str]:
    v = d.get(key) or []
    return v if isinstance(v, list) else [str(v)] if v else []


def baseline_classifier_node(state: ResearchState) -> dict[str, Any]:
    papers = list(state.get("verified_papers") or [])
    t0 = time.time()
    audit = dict(state.get("evidence_audit") or {})

    # Empty -> set zero counts only, no fake baseline.
    if not papers:
        trace = _emit("evidence_auditor", t0,
                      {"n_verified": 0, "no_papers": True},
                      {"n_baseline": 0, "n_parallel": 0, "n_survey": 0,
                       "n_dataset_paper": 0, "n_noise": 0},
                      [{"tool": "local.classifier", "mode": "empty"}],
                      "local", [])
        return {
            "baseline_candidates": [],
            "parallel_candidates": [],
            "dataset_papers": [],
            "surveys": [],
            "evidence_audit": {
                **audit,
                "baseline_n": 0,
                "parallel_n": 0,
                "survey_n": 0,
                "dataset_paper_n": 0,
                "noise_n": 0,
                "no_papers": True,
            },
            "trace_events": list(state.get("trace_events") or []) + [trace],
        }

    atoms = state.get("topic_atoms") or {}
    method_terms = [str(x).lower() for x in _word_list(atoms, "method")]
    object_terms = [str(x).lower() for x in _word_list(atoms, "object")]
    task_terms = [str(x).lower() for x in _word_list(atoms, "task")]
    avoid_terms = [str(x).lower() for x in _word_list(atoms, "avoid_terms")]

    baselines: list[dict[str, Any]] = []
    parallels: list[dict[str, Any]] = []
    dataset_papers: list[dict[str, Any]] = []
    surveys: list[dict[str, Any]] = []
    noise: list[dict[str, Any]] = []

    for p in papers:
        title = (p.get("title") or p.get("name") or "").strip()
        abstract = (p.get("abstract") or p.get("snippet") or "").lower()
        text = f"{title.lower()} {abstract}"
        rel = (p.get("relation_to_topic") or "").lower()
        stype = (p.get("source_type") or "paper").lower()

        hit_method = [t for t in method_terms if t and t in text]
        hit_object = [t for t in object_terms if t and t in text]
        hit_task = [t for t in task_terms if t and t in text]
        matched = hit_method + hit_object + hit_task
        unmatched_method = [t for t in method_terms if t and t not in text]
        unmatched_object = [t for t in object_terms if t and t not in text]
        unmatched_task = [t for t in task_terms if t and t not in text]
        unmatched = unmatched_method + unmatched_object + unmatched_task
        avoid_hit = [t for t in avoid_terms if t and t in text]

        why = ""
        next_use: str = "candidate_only"
        needs_audit = False

        # Survey detection (SOP §5.9): keywords + source_type — never baseline.
        is_survey = (
            stype == "survey"
            or "survey" in text
            or "review" in text
            or "systematic" in text
        )

        # Dataset-paper detection.
        is_dataset_paper = (
            stype == "dataset"
            or any(t in text for t in ("dataset", "benchmark dataset"))
        ) and rel in ("dataset_paper", "dataset_source", "")

        has_repro = bool(
            p.get("official_code_url") or p.get("project_page_url")
            or p.get("dataset_name") or any(
                k in text for k in ("github.com/", "code available", "released code",
                                    "open source our code"))
        )

        # Decide role.
        if is_survey and rel not in ("baseline", "parallel"):
            role = "survey"
        elif is_dataset_paper and rel not in ("baseline", "direct"):
            role = "dataset_paper"
        elif rel == "baseline" or (rel == "direct" and has_repro):
            role = "baseline"
        elif rel in ("parallel", "proxy"):
            role = "parallel"
        elif rel == "direct" and not has_repro:
            # direct paper that lacks reproducibility signals -> background
            role = "background"
        elif matched:
            # weak relation via topic axes only
            if len(matched) <= 1 or avoid_hit:
                role = "background"
            else:
                role = "parallel"
        else:
            role = "noise"

        if rel == "none" or (not matched and rel not in ("baseline", "parallel", "proxy")):
            role = "noise"

        # Ambiguity flag -> needs human/LLM audit (SOP §5.1.2).
        needs_audit = role == "background" and (len(matched) >= 2)

        # next_use mapping.
        if role == "baseline":
            next_use = "baseline"
            why = (f"{title} is explicitly cited as the starting reproducer/method "
                   f"for the topic (matched axes: {matched or ['topic']}).")
        elif role == "parallel":
            next_use = "parallel"
            why = (f"{title} addresses the same method+object spectrum via a "
                   f"different specific approach (matched: {matched or ['partial']}, "
                   f"unmatched: {unmatched or ['—']}).")
        elif role == "dataset_paper":
            next_use = "dataset_source"
            why = f"{title}'s primary contribution is a dataset/benchmark usable as evidence."
        elif role == "survey":
            next_use = "keyword_expand"
            why = f"{title} surveys the area; useful for related-work context only."
        elif role == "noise":
            next_use = "candidate_only"
            why = f"{title} matched no topic axes and is unrelated to the scope."
        else:
            next_use = "candidate_only"
            why = f"{title} provides weak methodological support only."

        classified = {
            **p,
            "role": role,
            "why_relevant": why,
            "matched_topic_axes": matched,
            "unmatched_topic_axes": unmatched,
            "next_use": next_use,
            "needs_human_or_llm_audit": needs_audit,
            "relation_to_topic": p.get("relation_to_topic") or role,
        }

        if role == "baseline":
            baselines.append(classified)
        elif role == "parallel":
            parallels.append(classified)
        elif role == "dataset_paper":
            dataset_papers.append(classified)
        elif role == "survey":
            surveys.append(classified)
        else:
            noise.append(classified)

    trace = _emit("evidence_auditor", t0,
                  {"n_verified": len(papers)},
                  {"n_baseline": len(baselines), "n_parallel": len(parallels),
                   "n_survey": len(surveys), "n_dataset_paper": len(dataset_papers),
                   "n_noise": len(noise)},
                  [{"tool": "local.classifier", "mode": "rule_based_topics"}],
                    "local", [])

    return {
        "baseline_candidates": baselines,
        "parallel_candidates": parallels,
        "dataset_papers": dataset_papers,
        "surveys": surveys,
        "evidence_audit": {
            **audit,
            "baseline_n": len(baselines),
            "parallel_n": len(parallels),
            "survey_n": len(surveys),
            "dataset_paper_n": len(dataset_papers),
            "noise_n": len(noise),
        },
        "trace_events": list(state.get("trace_events") or []) + [trace],
    }
