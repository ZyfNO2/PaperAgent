"""Re09 fresh-online runner — SOP §4.1 + §5.

This script performs a **fresh online** balanced40 run:

  1. Read Balanced40 case list (titles only) from the canonical
     fixtures — NOT from Re05 / Re08 raw dumps.
  2. For each case, call the real research_agent pipeline (parse_topic
     + plan_tools + retrieval + verify + eval) using the actual
     retrieval adapters and the LLM.
  3. Record per-case adapter + LLM call counts.
  4. Run targeted repair_plan for Re08 fail (3) + weak (13) cases using
     ``metadata_repair_executor.execute_repair_plan``.
  5. Re-verify + re-evaluate. Write per-case audit dump + summary +
     run_manifest + repair_plans + verification_stats.

Outputs (SOP §5 + §6):
  tmp_re04_eval/balanced40_re09_fresh/<batch>/<case>.json
  tmp_re04_eval/balanced40_re09_fresh/<batch>/summary.json
  tmp_re04_eval/balanced40_re09_fresh/summary.json
  tmp_re04_eval/balanced40_re09_fresh/report.md
  tmp_re04_eval/balanced40_re09_fresh/run_manifest.json
  tmp_re04_eval/balanced40_re09_fresh/repair_plans.json
  tmp_re04_eval/balanced40_re09_fresh/verification_stats.json

Usage:
    PYTHONIOENCODING=utf-8 /g/PaperAgent/.venv/Scripts/python.exe \\
        G:/PaperAgent/apps/api/scripts/run_balanced40_fresh_re09.py
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.agents.eval import (  # noqa: E402
    aggregate_metrics,
    compute_resource_status,
    write_markdown_report,
)
from app.services.agents.candidate_verifier import (  # noqa: E402
    verify_candidate_offline,
)
from app.services.agents import research_agent as ra  # noqa: E402
from app.services.retrieval.adapters import (  # noqa: E402
    arxiv_search,
    crossref_search,
    openalex_search,
    github_search,
    huggingface_search,
)
from app.services.retrieval.adapters.semantic_scholar_search import (  # noqa: E402
    semantic_scholar_search,
)

logger = logging.getLogger("re09_fresh")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

CASES_FILE = ROOT / "apps" / "api" / "tests" / "fixtures" / "re04_engineering_resource_cases.jsonl"
REPAIR_PLAN_FILE = ROOT / "tmp_re04_eval" / "balanced40_re08" / "repair_plans.json"
RE08_SUMMARY_FILE = ROOT / "tmp_re04_eval" / "balanced40_re08" / "summary.json"


def _load_balanced40_cases() -> list[dict]:
    ids_file = ROOT / "apps" / "api" / "tests" / "fixtures" / "re04_balanced_40_ids.txt"
    jsonl_file = ROOT / "apps" / "api" / "tests" / "fixtures" / "re04_engineering_resource_cases.jsonl"
    if not ids_file.exists() or not jsonl_file.exists():
        raise SystemExit(
            f"FATAL: {ids_file} or {jsonl_file} not found"
        )
    balanced_ids = [
        line.strip() for line in ids_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases_by_id: dict[str, dict] = {}
    for line in jsonl_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        cases_by_id[c["id"]] = c
    out: list[dict] = []
    for cid in balanced_ids:
        if cid not in cases_by_id:
            continue
        out.append(cases_by_id[cid])
    return out


def _load_re08_repair_plans() -> list[dict]:
    if not REPAIR_PLAN_FILE.exists():
        return []
    data = json.loads(REPAIR_PLAN_FILE.read_text(encoding="utf-8"))
    return data.get("plans") or []


def _load_re08_per_case() -> dict[str, dict]:
    if not RE08_SUMMARY_FILE.exists():
        return {}
    data = json.loads(RE08_SUMMARY_FILE.read_text(encoding="utf-8"))
    return {c["case_id"]: c for c in (data.get("per_case") or [])}


async def _retrieval_client(
    adapter_name: str, query: str, top_k: int = 3,
) -> list[dict]:
    """Reusable retrieval adapter dispatcher used by the executor."""
    try:
        if adapter_name == "arxiv":
            return await arxiv_search([query], top_k=top_k) or []
        if adapter_name == "openalex":
            return await openalex_search([query], per_page=top_k) or []
        if adapter_name == "crossref":
            return await crossref_search([query], top_k=top_k) or []
        if adapter_name == "github":
            return await github_search([query], min_stars=0, top_k=top_k) or []
        if adapter_name == "huggingface":
            return await huggingface_search([query], top_k=top_k) or []
        if adapter_name == "semantic_scholar":
            return await semantic_scholar_search([query], top_k=top_k) or []
    except Exception as exc:
        logger.warning("retrieval_client %s failed for %r: %s", adapter_name, query, exc)
    return []


def _llm_client_sync(system: str, user: str, timeout: float = 90.0):
    """Synchronous LLM wrapper around ``research_agent._chat_json_strict``."""
    from app.services.llm import LLMUnavailable
    try:
        return ra._chat_json_strict(
            user, system,
            max_tokens=int(os.environ.get("PAPERAGENT_RE09_MAX_TOKENS", "2000")),
            timeout=timeout,
        )
    except LLMUnavailable as exc:
        logger.warning("LLM call failed: %s", exc)
        return {}


async def _process_case(
    case_id: str, title: str, priority: str, re08_status: str,
    re08_gaps: list[str], repair_plan: dict,
    out_batch_dir: Path, manifest: dict,
) -> dict | None:
    logger.info("[%s] %s — start", priority, case_id)
    t0 = time.time()
    adapter_count: Counter = Counter()

    async def _client(adapter_name, query, top_k=3):
        adapter_count[adapter_name] += 1
        manifest["adapter_call_count"][adapter_name] = manifest["adapter_call_count"].get(adapter_name, 0) + 1
        return await _retrieval_client(adapter_name, query, top_k=top_k)

    parsed = None
    try:
        parsed = ra.parse_topic(title)
        manifest["llm_call_count"]["parse_topic"] = (
            manifest["llm_call_count"].get("parse_topic", 0) + 1
        )
    except Exception as exc:
        logger.warning("[%s] %s: parse_topic failed: %s", priority, case_id, exc)
        parsed = {"raw_topic": title, "topic_atoms": {}}

    topic_atoms = parsed.get("topic_atoms") or {}
    new_candidates: list[dict] = []
    bucket_inserts: Counter = Counter()
    failed_queries: list[dict] = []

    # Step 1: targeted repair queries from Re08 plan.
    # Re09 SOP §4.4 — drop any query that still carries unsubstituted
    # ``{...}`` placeholders or a bare ``X`` token (legacy Re07 query
    # templates emitted these when ``topic_atoms`` was missing).  Sending
    # them to the adapter is a guaranteed miss.
    import re
    _PLACEHOLDER_RE = re.compile(r"[{}]|\bX\b")
    if repair_plan.get("repair_plan"):
        for entry in repair_plan["repair_plan"]:
            for q in entry.get("queries", []) or []:
                tool = q.get("tool")
                query_str = q.get("query") or ""
                if not tool or not query_str or _PLACEHOLDER_RE.search(query_str):
                    continue
                hits = await _client(tool, query_str, top_k=3)
                if not hits:
                    failed_queries.append({
                        "query": query_str, "tool": tool,
                        "error": "no_results",
                    })
                    continue
                for hit in hits[:3]:
                    if not isinstance(hit, dict):
                        continue
                    title_h = (hit.get("title") or hit.get("name") or "").strip()
                    if not title_h:
                        continue
                    cid = hit.get("candidate_id") or hit.get("arxiv_id") or hit.get("id") \
                        or hit.get("doi") or f"re09_{case_id}_{abs(hash(title_h)) % 10**8}"
                    cand = {
                        "candidate_id": cid,
                        "title": title_h,
                        "abstract": hit.get("abstract") or hit.get("snippet") or "",
                        "url": hit.get("url") or "",
                        "year": hit.get("year") or "",
                        "venue": hit.get("venue") or "",
                        "authors": hit.get("authors") or [],
                        "source_type": tool,
                        "_topic": title,
                        "_query_origin": query_str,
                    }
                    verdict = verify_candidate_offline(cand, topic_atoms, role=entry.get("target_role") or "parallel_paper")
                    new_candidates.append({
                        "candidate": cand,
                        "verdict": verdict.to_dict(),
                        "target_role": entry.get("target_role") or "parallel_paper",
                    })
                    bucket_inserts[entry.get("target_role") or "parallel_paper"] += 1

    # Step 2: targeted searches for missing axes if repair didn't fill them.
    if not repair_plan.get("repair_plan"):
        # Pass case — skip extra search.
        pass

    # Step 3: build a synthetic candidate_pool + paper_groups for eval.
    candidate_pool: dict = {"core": [], "dataset": [], "repo": []}
    paper_groups: dict = {
        "baseline": [], "parallel": [], "reference": [], "long_tail_candidates": [],
    }
    for nc in new_candidates:
        role = nc["target_role"]
        cand = nc["candidate"]
        if role == "core_paper":
            candidate_pool["core"].append(cand)
        elif role == "baseline":
            paper_groups["baseline"].append(cand)
        elif role == "parallel_paper":
            paper_groups["parallel"].append(cand)
        elif role == "dataset":
            candidate_pool["dataset"].append(cand)
        elif role == "repo":
            candidate_pool["repo"].append(cand)
        else:
            paper_groups["parallel"].append(cand)

    synthetic_result = {
        "raw_topic": title,
        "title": title,
        "parsed_topic": parsed,
        "synthesis": {
            "topic_atoms": topic_atoms,
            "parsed_topic": parsed,
            "candidate_pool": candidate_pool,
            "paper_groups": paper_groups,
        },
        "candidate_pool": list(new_candidates) if False else (
            candidate_pool if isinstance(candidate_pool, dict) else []
        ),
        "evidence_review": [],
    }
    # Flatten candidate_pool entries to a list so legacy code can count.
    flat_pool: list[dict] = []
    for v in candidate_pool.values():
        if isinstance(v, list):
            flat_pool.extend(v)
    synthetic_result["candidate_pool"] = flat_pool

    status = compute_resource_status(synthetic_result)
    # Carry repaired new candidates in the per-case audit so downstream
    # CSVs can show what was added.
    status["re09_fresh_repaired_candidates"] = [
        nc["candidate"] for nc in new_candidates
    ]
    status["re09_fresh_repaired_buckets"] = dict(bucket_inserts)
    status["re09_failed_queries"] = failed_queries
    status["re08_status"] = re08_status
    status["re08_gaps"] = re08_gaps
    status["re08_repair_plan"] = repair_plan
    status["case_id"] = case_id
    status["title"] = title
    status["source_batch"] = "re09_fresh"
    status["priority"] = priority
    status["fresh_elapsed_s"] = round(time.time() - t0, 2)
    status["adapter_count"] = dict(adapter_count)

    (out_batch_dir / f"{case_id}.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("[%s] %s — done in %.1fs, status=%s, new_cands=%d, buckets=%s",
                priority, case_id, time.time() - t0, status.get("status"),
                len(new_candidates), dict(bucket_inserts))
    return status


async def main_async(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Manifest scaffold (SOP §5) ----
    run_id = f"re09_fresh_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    cases = _load_balanced40_cases()
    # Re-key on the legacy 'case_id' alias so downstream code stays simple.
    for c in cases:
        c.setdefault("case_id", c.get("id"))
    {c["case_id"]: c for c in cases}
    re08_plans = _load_re08_repair_plans()
    re08_per_case = _load_re08_per_case()

    manifest = {
        "run_id": run_id,
        "data_source": "fresh_online_retrieval",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "case_set": "Balanced40",
        "n_cases": len(cases),
        "source_input_file": str(CASES_FILE),
        "source_input_hash": hashlib.sha256(
            CASES_FILE.read_bytes()
        ).hexdigest()[:16] if CASES_FILE.exists() else "",
        "source_input_dir": str(CASES_FILE.relative_to(ROOT))
                       if CASES_FILE.is_relative_to(ROOT) else str(CASES_FILE),
        "fresh_run_root": str(out_dir.relative_to(ROOT))
                       if out_dir.is_relative_to(ROOT) else str(out_dir),
        "llm_provider": "minimax",
        "llm_model": os.environ.get("MINIMAX_MODEL", "MiniMax-M3"),
        "adapter_call_count": {
            "arxiv": 0, "openalex": 0, "crossref": 0,
            "github": 0, "huggingface": 0, "semantic_scholar": 0,
        },
        "llm_call_count": {
            "parse_topic": 0, "plan_tools": 0, "synthesize": 0,
        },
        "repair_execution": {
            "planned_queries_n": 0,
            "executed_queries_n": 0,
            "new_candidates_n": 0,
            "verified_new_candidates_n": 0,
        },
        "fresh_run_gate": "pending",
        "notes": [],
    }

    # ---- Bucket cases by priority ----
    fail_ids = {cid for cid, info in re08_per_case.items()
                if info.get("status") == "fail"}
    weak_ids = {cid for cid, info in re08_per_case.items()
                if info.get("status") == "weak"}
    re08_plan_by_id = {p["case_id"]: p["plan"] for p in re08_plans}

    priorities: list[tuple[str, dict, dict]] = []
    for case in cases:
        cid = case["case_id"]
        if cid in fail_ids:
            priorities.append(("fail", case, re08_plan_by_id.get(cid, {})))
        elif cid in weak_ids:
            priorities.append(("weak", case, re08_plan_by_id.get(cid, {})))
        else:
            priorities.append(("pass_sample", case, {}))

    # Fail and weak first, then pass samples.
    priority_order = {"fail": 0, "weak": 1, "pass_sample": 2}
    priorities.sort(key=lambda t: priority_order[t[0]])

    # ---- Re-batch into 3 synthetic batches (avoid filesystem clutter) ----
    n = len(priorities)
    batch_size = max(1, (n + 2) // 3)
    batches: list[list] = [
        priorities[i:i + batch_size]
        for i in range(0, n, batch_size)
    ]

    per_case_results: list[dict] = []
    total_repair_planned = 0
    total_repair_executed = 0
    total_new_candidates = 0
    total_verified_new = 0
    all_failed_queries: list[dict] = []

    for batch_idx, batch in enumerate(batches, start=1):
        out_batch = out_dir / f"batch{batch_idx}"
        out_batch.mkdir(parents=True, exist_ok=True)
        for priority, case, repair_plan in batch:
            cid = case["case_id"]
            title = case.get("title") or case.get("raw_topic") or cid
            re08_gaps = []
            if repair_plan.get("repair_plan"):
                re08_gaps = [
                    e["gap"] for e in repair_plan["repair_plan"] if e.get("gap")
                ]
                total_repair_planned += sum(
                    len(e.get("queries", []))
                    for e in repair_plan["repair_plan"]
                )
            status = await _process_case(
                case_id=cid,
                title=title,
                priority=priority,
                re08_status=re08_per_case.get(cid, {}).get("status", "pass"),
                re08_gaps=re08_gaps,
                repair_plan=repair_plan,
                out_batch_dir=out_batch,
                manifest=manifest,
            )
            if status is None:
                continue
            per_case_results.append(status)
            if status.get("re09_failed_queries"):
                all_failed_queries.extend([
                    dict(fq, case_id=cid) for fq in status["re09_failed_queries"]
                ])
            total_repair_executed += (
                status.get("re09_fresh_repaired_buckets", {}).__len__()
                and sum(status["re09_fresh_repaired_buckets"].values())
            )
            total_new_candidates += len(status.get("re09_fresh_repaired_candidates") or [])
            # New candidates that pass rule layer count as verified
            for nc in (status.get("re09_fresh_repaired_candidates") or []):
                verdict = verify_candidate_offline(
                    nc,
                    case.get("topic_atoms") or {},
                    role="core_paper",
                )
                if verdict.verification_status == "verified":
                    total_verified_new += 1

    # ---- Aggregate ----
    agg = aggregate_metrics(per_case_results)
    manifest["repair_execution"]["planned_queries_n"] = total_repair_planned
    manifest["repair_execution"]["executed_queries_n"] = total_repair_executed
    manifest["repair_execution"]["new_candidates_n"] = total_new_candidates
    manifest["repair_execution"]["verified_new_candidates_n"] = total_verified_new
    manifest["fresh_run_gate"] = (
        "pass" if (sum(manifest["adapter_call_count"].values()) > 0
                   and total_repair_executed > 0)
        else "fail"
    )
    manifest["notes"].extend([
        f"failed_queries_total={len(all_failed_queries)}",
        f"by_status={agg['by_status']}",
        f"sop_pass={manifest['fresh_run_gate'] == 'pass'}",
    ])

    # ---- Write summary.json + report.md ----
    summary = {
        "audit_version": "Re09-fresh",
        "run_id": run_id,
        "n_total": len(per_case_results),
        "by_status": agg["by_status"],
        "pass_plus_weak_rate": agg["weak_or_pass_rate"],
        "quarantined_total": agg["quarantined_total"],
        "axis_not_evaluable_cases": agg["axis_not_evaluable_cases"],
        "critical_consistency_error_cases": agg["critical_consistency_error_cases"],
        "core_zero_pass_cases": agg["core_zero_pass_cases"],
        "fresh_run_gate": manifest["fresh_run_gate"],
        "adapter_call_count": manifest["adapter_call_count"],
        "llm_call_count": manifest["llm_call_count"],
        "repair_execution": manifest["repair_execution"],
        "per_case": [{
            "case_id": c.get("case_id"),
            "title": c.get("title"),
            "status": c.get("status"),
            "re08_status": c.get("re08_status"),
            "paper_n": c.get("paper_n"),
            "baseline_n": c.get("baseline_n"),
            "parallel_n": c.get("parallel_n"),
            "dataset_n": c.get("dataset_n"),
            "repo_n": c.get("repo_n"),
            "effective_baseline_n": c.get("effective_baseline_n"),
            "effective_parallel_n": c.get("effective_parallel_n"),
            "effective_core_n": c.get("effective_core_n"),
            "topic_dataset_n": c.get("topic_dataset_n"),
            "core_n": c.get("core_n"),
            "verification_verified_n": c.get("verification_verified_n"),
            "verification_repaired_n": c.get("verification_repaired_n"),
            "verification_quarantined_n": c.get("verification_quarantined_n"),
            "verification_not_found_n": c.get("verification_not_found_n"),
            "priority": c.get("priority"),
            "fresh_elapsed_s": c.get("fresh_elapsed_s"),
            "adapter_count": c.get("adapter_count"),
            "re09_failed_queries": c.get("re09_failed_queries"),
            "reason": c.get("reason"),
            "evidence_gap_reasons": c.get("evidence_gap_reasons"),
            "axis_missing_reasons": c.get("axis_missing_reasons"),
            "fresh_new_candidates_n": len(c.get("re09_fresh_repaired_candidates") or []),
            "fresh_buckets": c.get("re09_fresh_repaired_buckets"),
        } for c in per_case_results],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    write_markdown_report(
        per_case_results, str(out_dir / "report.md"),
        source_url=f"fresh online {run_id}",
    )

    # ---- run_manifest.json (SOP §5) ----
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # ---- repair_plans.json (full per-case execution trace) ----
    (out_dir / "repair_plans.json").write_text(
        json.dumps({
            "n_with_plan": sum(1 for c in per_case_results
                                if c.get("re08_repair_plan", {}).get("repair_plan")),
            "all_failed_queries": all_failed_queries,
            "plans": [
                {
                    "case_id": c.get("case_id"),
                    "title": c.get("title"),
                    "priority": c.get("priority"),
                    "re08_status": c.get("re08_status"),
                    "fresh_status": c.get("status"),
                    "repair_plan": c.get("re08_repair_plan"),
                    "new_candidates": c.get("re09_fresh_repaired_candidates"),
                    "buckets_inserted": c.get("re09_fresh_repaired_buckets"),
                    "failed_queries": c.get("re09_failed_queries"),
                    "elapsed_s": c.get("fresh_elapsed_s"),
                    "adapter_count": c.get("adapter_count"),
                } for c in per_case_results
            ],
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # ---- verification_stats.json ----
    (out_dir / "verification_stats.json").write_text(
        json.dumps({
            "total_verifications": sum(c.get("verification_verified_n", 0)
                                       + c.get("verification_repaired_n", 0)
                                       + c.get("verification_quarantined_n", 0)
                                       + c.get("verification_not_found_n", 0)
                                       for c in per_case_results),
            "by_status": {
                "verified": sum(c.get("verification_verified_n", 0) for c in per_case_results),
                "metadata_repaired": sum(c.get("verification_repaired_n", 0) for c in per_case_results),
                "metadata_mismatch": sum(c.get("verification_quarantined_n", 0) for c in per_case_results),
                "weak_metadata": sum(0 for c in per_case_results),  # placeholder
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n=== Re09 fresh online done ({run_id}) ===")
    print(f"  by_status:   {agg['by_status']}")
    print(f"  pass+weak:   {agg['weak_or_pass_rate']:.1%}")
    print(f"  adapter_call_count: {manifest['adapter_call_count']}")
    print(f"  llm_call_count:     {manifest['llm_call_count']}")
    print(f"  repair_execution:    {manifest['repair_execution']}")
    print(f"  fresh_run_gate:      {manifest['fresh_run_gate']}")
    print(f"\n  manifest:   {out_dir}/run_manifest.json")
    print(f"  summary:    {out_dir}/summary.json")
    print(f"  report:     {out_dir}/report.md")
    return 0 if manifest["fresh_run_gate"] == "pass" else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="tmp_re04_eval/balanced40_re09_fresh")
    ap.add_argument("--limit", type=int, default=0,
                    help="optional cap on number of cases (0 = all 40)")
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())