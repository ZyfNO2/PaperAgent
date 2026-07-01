"""Generic trace for one topic. Used by subagents to run 53/55/59 in parallel.

Usage:  uv run python tmp_s66v_trace_topic.py --topic "<raw topic>" --out tmp_s66v_traces/<name>.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps", "api"))

from app.services.agents.research_agent import (
    run_research_agent,
    reset_counter,
    GLOBAL_COUNTER,
    GLOBAL_SUSPEND_STATE,
)


# S66 ground truth table — used for verifier scoring only.
GROUND_TRUTH_TABLE = {
    "59 机器学习在水声数据分类识别中的应用": {
        "baseline_titles": [
            "A Spatio-temporal Deep Learning Approach for Underwater Acoustic Signals Classification",
            "An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data",
        ],
        "parallel_titles": [
            "Cross-Domain Knowledge Transfer for Underwater Acoustic Classification Using Pre-trained Models",
            "Underwater Acoustic Target Recognition based on Smoothness-inducing Regularization",
            "Underwater Acoustic Target Recognition on ShipsEar Dataset",
        ],
        "dataset_names": ["DeepShip", "ShipsEar", "SonAIr"],
        "repo_names": ["zakaria76al/USC", "lucascesarfd/underwater_snd", "PANN_Models_DeepShip"],
    },
    "53 基于国六标准的重型柴油车远程排放监控系统研发": {
        "baseline_titles": [
            "OBD-based remote diesel emission monitoring",
            "Heavy-duty diesel engine OBD remote diagnostics framework",
        ],
        "parallel_titles": [
            "Telematics-based vehicle emission analytics",
            "Remote OBD monitoring for compliance reporting",
        ],
        "dataset_names": ["OBD-II fault dataset", "China-VI compliance dataset", "fleet telematics dataset"],
        "repo_names": ["python-OBD/python-OBD", "eclipse-sumo/sumo", "cantools/cantools"],
    },
    "55 无条件稳定FDTD在微波传输线中的应用研究": {
        "baseline_titles": [
            "Unconditionally stable FDTD for transmission line analysis",
            "FDTD Method for Microwave Transmission Lines",
        ],
        "parallel_titles": [
            "Alternating-direction-implicit FDTD for microwave structures",
            "Crank-Nicolson FDTD for waveguide analysis",
        ],
        "dataset_names": ["openEMS benchmark", "Meep reference benchmarks"],
        "repo_names": ["thliebig/openEMS", "NanoComp/meep", "gprMax/gprMax"],
    },
}


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def _fuzzy(needle: str, candidates: list[str]) -> bool:
    n = _normalize(needle)
    nws = n.split()
    ngrams4 = {" ".join(nws[i:i + 4]) for i in range(len(nws) - 3)}
    sig_words = {w for w in nws if len(w) > 4}
    for c in candidates:
        if not c:
            continue
        cn = _normalize(c)
        if not cn:
            continue
        if n in cn or cn in n:
            return True
        cws = cn.split()
        cgrams4 = {" ".join(cws[i:i + 4]) for i in range(len(cws) - 3)}
        if len(ngrams4 & cgrams4) >= 2:
            return True
        csig = {w for w in cws if len(w) > 4}
        if sig_words and csig:
            ratio = len(sig_words & csig) / max(1, len(sig_words))
            if ratio >= 0.55:
                return True
    return False


def _hit(rows: list[str], gt: list[str]) -> dict:
    hits = [g for g in gt if _fuzzy(g, rows)]
    return {"hit": hits, "miss": [g for g in gt if g not in hits]}


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--include-papers-search", default=None,
                   help="Optional: comma-separated repo names to enable backfill search")
    args = p.parse_args()
    topic = args.topic
    reset_counter()
    started = time.time()
    result = await run_research_agent(topic)
    elapsed = time.time() - started

    titles_paper = []
    for cat in ["baseline_papers", "parallel_papers", "module_papers", "reference_papers"]:
        titles_paper.extend([(r.get("title") or "") for r in (result.buckets.get(cat) or [])])
    titles_dataset = [
        (r.get("name") or r.get("title") or "")
        for r in (result.buckets.get("dataset_candidates") or [])
    ]
    titles_repo = [
        (r.get("title") or r.get("name") or "")
        for r in (result.buckets.get("repo_candidates") or [])
    ]

    gt = GROUND_TRUTH_TABLE.get(topic, {
        "baseline_titles": [], "parallel_titles": [], "dataset_names": [], "repo_names": [],
    })

    hits = {
        "papers_baseline": _hit(titles_paper, gt["baseline_titles"]),
        "papers_parallel": _hit(titles_paper, gt["parallel_titles"]),
        "datasets":        _hit(titles_dataset + titles_paper, gt["dataset_names"]),
        "repos":           _hit(titles_repo + titles_paper, gt["repo_names"]),
    }

    total_gt = sum(len(gt[k]) for k in ["baseline_titles", "parallel_titles", "dataset_names", "repo_names"])
    total_hit = sum(len(hits[k]["hit"]) for k in hits)
    summary = {
        "topic": topic,
        "elapsed_sec": round(elapsed, 2),
        "llm_calls": result.llm_calls,
        "llm_failures": result.llm_failures,
        "domain_route": result.parsed_topic.get("domain_route"),
        "query_atoms_en": result.parsed_topic.get("query_atoms_en"),
        "raw_tool_sizes": {k: len(v) for k, v in result.raw_tool_results.items()},
        "overall_verdict": result.overall_verdict,
        "suspended_adapters": sorted([
            (a, GLOBAL_SUSPEND_STATE.suspended_until_str(a))
            for a in ("arxiv", "openalex", "crossref", "github")
            if GLOBAL_SUSPEND_STATE.is_suspended(a)
        ]),
        "buckets": {k: [(r.get("title") or r.get("name") or "") for r in (result.buckets.get(k) or [])]
                    for k in ["baseline_papers", "parallel_papers", "module_papers",
                              "reference_papers", "dataset_candidates", "repo_candidates"]},
        "evidence_gaps": result.buckets.get("evidence_gaps") or [],
        "fabrication_alerts": result.fabrication_alerts,
        "hit_rates": hits,
        "total": {"gt": total_gt, "hit": total_hit, "rate": round(total_hit / max(1, total_gt), 2)},
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    # Pretty-print
    print(f"[{topic[:30]}...] {elapsed:.1f}s, llm={result.llm_calls} (fail={result.llm_failures})")
    print(f"  domain={summary['domain_route']}")
    print(f"  raw sizes: {summary['raw_tool_sizes']}")
    print(f"  hits: baseline={len(hits['papers_baseline']['hit'])}/{len(gt['baseline_titles'])} "
          f"parallel={len(hits['papers_parallel']['hit'])}/{len(gt['parallel_titles'])} "
          f"datasets={len(hits['datasets']['hit'])}/{len(gt['dataset_names'])} "
          f"repos={len(hits['repos']['hit'])}/{len(gt['repo_names'])}")
    print(f"  TOTAL: {total_hit}/{total_gt} = {summary['total']['rate']*100:.0f}%")
    print(f"  buckets:")
    for cat, items in summary["buckets"].items():
        print(f"    {cat}: {len(items)}")
        for t in items[:6]:
            print(f"      - {t[:100]}")
    if summary["evidence_gaps"]:
        print(f"  gaps:")
        for g in summary["evidence_gaps"]:
            print(f"      - {g[:100]}")
    if summary["fabrication_alerts"]:
        print(f"  fabrication alerts: {len(summary['fabrication_alerts'])}")


if __name__ == "__main__":
    asyncio.run(main())
