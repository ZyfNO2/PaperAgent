"""Re10 reflection-loop runner — SOP §4.6.

Reads Balanced40 case list.  For each case:
  1. Loads seed candidates from Re08 raw dump + Re09 fresh run.
  2. Calls ``run_search_reflection_loop`` (built in Re10 Phase A).
  3. Records the loop's TraceLedger JSON as a per-case dump.
  4. After all cases, computes compute_resource_status on the
     incremental candidate pool and writes summary.

Inputs:
  - apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl
  - apps/api/tests/fixtures/re04_balanced_40_ids.txt
  - tmp_re04_eval/balanced40/           (Re05 LLM-online raw dump — Re08 seed)
  - tmp_re04_eval/balanced40_re09_fresh/  (Re09 fresh run summary)

Outputs (SOP §11):
  - tmp_re04_eval/balanced40_re10_reflection/traces/<case>.json
  - tmp_re04_eval/balanced40_re10_reflection/batch<n>/<case>.json
  - tmp_re04_eval/balanced40_re10_reflection/summary.json
  - tmp_re04_eval/balanced40_re10_reflection/run_manifest.json
  - tmp_re04_eval/balanced40_re10_reflection/reflection_stats.json
  - tmp_re04_eval/balanced40_re10_reflection/report.md

History: this runner replaces run_balanced40_fresh_re09.py as the
production search entry point.  Re09 runner is kept as historical
artifact only (per SOP §4.6).
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

logger = logging.getLogger("re10_reflection")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

CASES_FILE = ROOT / "apps" / "api" / "tests" / "fixtures" / "re04_engineering_resource_cases.jsonl"
IDS_FILE = ROOT / "apps" / "api" / "tests" / "fixtures" / "re04_balanced_40_ids.txt"
RE05_DIR = ROOT / "tmp_re04_eval" / "balanced40"
RE07_DIR = ROOT / "tmp_re04_eval" / "balanced40_re07"
RE08_DIR = ROOT / "tmp_re04_eval" / "balanced40_re08"
RE09_DIR = ROOT / "tmp_re04_eval" / "balanced40_re09_fresh"


def _load_balanced40_cases(ids_file: Path | None = None) -> list[dict]:
    if ids_file is not None:
        ids_file = Path(ids_file)
    balanced_ids = [
        ln.strip() for ln in (ids_file.read_text(encoding="utf-8").splitlines() if ids_file else IDS_FILE.read_text(encoding="utf-8").splitlines())
        if ln.strip()
    ]
    cases_by_id: dict[str, dict] = {}
    for ln in CASES_FILE.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        c = json.loads(ln)
        cases_by_id[c["id"]] = c
    return [cases_by_id[i] for i in balanced_ids if i in cases_by_id]


def _load_re08_seeds() -> dict[str, list[dict]]:
    """Index Re05 LLM-online raw dump + Re08 audit dump → per-case seed.

    Seeds are the union of:
      - Re05 top-level candidate_pool (titles + urls)
      - Re08 paper_groups.{baseline, parallel, reference}
      - Re08 candidate_pool.{core, dataset, repo}
    """
    seeds: dict[str, list[dict]] = {}
    if not RE05_DIR.exists():
        return seeds
    for batch_dir in sorted(RE05_DIR.iterdir()):
        if not batch_dir.is_dir():
            continue
        for case_path in sorted(batch_dir.glob("ENG-THESIS-*.json")):
            cid = case_path.stem
            try:
                dump = json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            seeds[cid] = []
            for c in (dump.get("candidate_pool") or []):
                if isinstance(c, dict):
                    c2 = dict(c)
                    c2["source_run"] = "re08"
                    seeds[cid].append(c2)
            syn = dump.get("synthesis") or {}
            for bucket in ("baseline", "parallel", "reference", "long_tail_candidates"):
                for c in ((syn.get("paper_groups") or {}).get(bucket) or []):
                    if isinstance(c, dict):
                        c2 = dict(c)
                        c2["source_run"] = "re08"
                        c2["source_bucket"] = bucket
                        seeds[cid].append(c2)
            for bucket in ("core", "dataset", "repo"):
                for c in ((syn.get("candidate_pool") or {}).get(bucket) or []):
                    if isinstance(c, dict):
                        c2 = dict(c)
                        c2["source_run"] = "re08"
                        c2["source_bucket"] = bucket
                        seeds[cid].append(c2)
    return seeds


def _load_re09_seeds() -> dict[str, list[dict]]:
    """Index Re09 fresh candidates per case from the per-case audit dumps."""
    seeds: dict[str, list[dict]] = {}
    if not RE09_DIR.exists():
        return seeds
    for batch_dir in sorted(RE09_DIR.iterdir()):
        if not batch_dir.is_dir():
            continue
        for case_path in sorted(batch_dir.glob("ENG-THESIS-*.json")):
            cid = case_path.stem
            try:
                dump = json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            seeds[cid] = []
            for c in (dump.get("re09_fresh_repaired_candidates") or []):
                if isinstance(c, dict):
                    c2 = dict(c)
                    c2["source_run"] = "re09"
                    seeds.setdefault(cid, []).append(c2)
    return seeds


def _merge_seeds(re08: dict[str, list], re09: dict[str, list]) -> dict[str, list]:
    """Union dedup by normalized title / DOI / arxiv_id."""
    merged: dict[str, list] = {}
    for cid in set(re08) | set(re09):
        seen: set[str] = set()
        items: list[dict] = []
        for c in (re08.get(cid) or []) + (re09.get(cid) or []):
            if not isinstance(c, dict):
                continue
            key = (
                (c.get("doi") or c.get("arxiv_id") or "").lower()
                or ("t:" + (c.get("title") or "").strip().lower()[:80])
            )
            if key in seen:
                continue
            seen.add(key)
            items.append(c)
        merged[cid] = items
    return merged


async def _run_llm(system: str, user: str) -> dict:
    """Async LLM wrapper."""
    from app.services.agents import research_agent as ra
    from app.services.llm import LLMUnavailable
    try:
        out = ra._chat_json_strict(
            user, system,
            max_tokens=int(os.environ.get("PAPERAGENT_RE10_MAX_TOKENS", "2000")),
            timeout=90.0,
        )
    except LLMUnavailable as exc:
        logger.warning("LLM call failed: %s", exc)
        return {}
    if isinstance(out, dict):
        return out
    if isinstance(out, str):
        try:
            return json.loads(out)
        except Exception:
            return {}
    return {}


def _build_retrieval_clients(loop_module) -> dict:
    """Build a {tool_name: async_callable} dict for the loop."""
    async def _arxiv(query: str, top_k: int = 3):
        from app.services.retrieval.adapters import arxiv_search
        return await arxiv_search([query], top_k=top_k) or []
    async def _openalex(query: str, top_k: int = 3):
        from app.services.retrieval.adapters import openalex_search
        return await openalex_search([query], per_page=top_k) or []
    async def _crossref(query: str, top_k: int = 3):
        from app.services.retrieval.adapters import crossref_search
        return await crossref_search([query], top_k=top_k) or []
    async def _github(query: str, top_k: int = 3):
        from app.services.retrieval.adapters import github_search
        return await github_search([query], min_stars=0, top_k=top_k) or []
    async def _huggingface(query: str, top_k: int = 3):
        from app.services.retrieval.adapters import huggingface_search
        return await huggingface_search([query], top_k=top_k) or []
    return {
        "arxiv": _arxiv, "openalex": _openalex, "crossref": _crossref,
        "github": _github, "huggingface": _huggingface,
    }


async def main_async(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"re10_refl_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # ---- Manifest scaffold (SOP §5 + Re09 compatibility) ----
    cases = _load_balanced40_cases(args.ids_file)
    # Re-key on the legacy 'case_id' alias so downstream code stays simple.
    for c in cases:
        c.setdefault("case_id", c.get("id"))
    re08_seeds = _load_re08_seeds()
    re09_seeds = _load_re09_seeds()
    seeds = _merge_seeds(re08_seeds, re09_seeds)

    manifest = {
        "run_id": run_id,
        "data_source": "reflection_loop_search",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "case_set": "Balanced40",
        "n_cases": len(cases),
        "source_input_file": str(CASES_FILE.relative_to(ROOT)) if CASES_FILE.is_relative_to(ROOT) else str(CASES_FILE),
        "source_input_hash": hashlib.sha256(CASES_FILE.read_bytes()).hexdigest()[:16],
        "source_input_dir": str(CASES_FILE.relative_to(ROOT)) if CASES_FILE.is_relative_to(ROOT) else str(CASES_FILE),
        "fresh_run_root": str(out_dir.relative_to(ROOT)) if out_dir.is_relative_to(ROOT) else str(out_dir),
        "llm_provider": "minimax",
        "llm_model": os.environ.get("MINIMAX_MODEL", "MiniMax-M3"),
        "adapter_call_count": {
            "arxiv": 0, "openalex": 0, "crossref": 0,
            "github": 0, "huggingface": 0,
        },
        "llm_call_count": {
            "domain_scout": 0, "reflection_critic": 0, "query_repair": 0,
        },
        "round_stats": {
            "rounds_total": 0, "stop_sufficient_evidence": 0,
            "stop_no_new_signal": 0, "stop_max_rounds": 0, "stop_blocked": 0,
        },
        "seed_stats": {
            "re08_seeds_total": sum(len(v) for v in re08_seeds.values()),
            "re09_seeds_total": sum(len(v) for v in re09_seeds.values()),
        },
        "trace_coverage": {
            "with_trace": 0, "missing_trace": 0,
        },
        "fresh_run_gate": "pending",
        "notes": [],
    }

    # ---- Import Re10 modules (built by subagent) ----
    try:
        from app.services.agents import search_reflection_loop as srl
    except ImportError as exc:
        logger.error("Re10 module not built yet: %s", exc)
        # Save manifest so validator can still check sub-gates
        (out_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("FATAL: Re10 modules not built. Run subagent first.")
        return 2

    retrieval_clients = _build_retrieval_clients(srl)

    async def _llm_client(system: str, user: str) -> dict:
        return await _run_llm(system, user)

    per_case_results: list[dict] = []
    n_batches = max(1, (len(cases) + 9) // 10)  # ~10 per batch
    batch_size = (len(cases) + n_batches - 1) // n_batches

    for batch_idx in range(n_batches):
        batch_cases = cases[batch_idx * batch_size:(batch_idx + 1) * batch_size]
        out_batch = out_dir / f"batch{batch_idx + 1}"
        out_batch.mkdir(parents=True, exist_ok=True)
        for case in batch_cases:
            cid = case["case_id"]
            title = case.get("title") or case.get("raw_topic") or cid
            # Get topic_atoms: try LLM fresh parse first, else Re08/Re09 atoms
            topic_atoms: dict = {}
            try:
                from app.services.agents.research_agent import parse_topic
                parsed = parse_topic(title)
                topic_atoms = parsed.get("topic_atoms") or {}
            except Exception:
                topic_atoms = {}
            if not topic_atoms:
                # Fallback: read from Re09 per-case
                for batch_dir in (RE09_DIR.iterdir() if RE09_DIR.exists() else []):
                    p = batch_dir / f"{cid}.json"
                    if p.exists():
                        try:
                            c = json.loads(p.read_text(encoding="utf-8"))
                            t = (c.get("synthesis") or {}).get("topic_atoms") or {}
                            if t:
                                topic_atoms = t
                                break
                        except Exception:
                            pass
            seed = seeds.get(cid, [])

            t0 = time.time()
            try:
                result = await srl.run_search_reflection_loop(
                    topic=title,
                    topic_atoms=topic_atoms,
                    seed_candidates=seed,
                    out_dir=str(out_dir),
                    case_id=cid,
                    max_rounds=3,
                    llm_client=_llm_client,
                    retrieval_clients=retrieval_clients,
                )
            except Exception as exc:
                logger.warning("[%s] loop failed: %s", cid, exc)
                result = {
                    "topic": title, "rounds": [],
                    "final_candidate_pool": {"core": [], "baseline": [],
                                              "parallel": [], "dataset": [],
                                              "repo": []},
                    "stop_reason": "blocked", "summary": {},
                    "trace_path": "",
                    "error": str(exc),
                }
            result["case_id"] = cid
            result["title"] = title
            result["source_batch"] = f"batch{batch_idx + 1}"
            result["elapsed_s"] = round(time.time() - t0, 2)
            result["seed_n"] = len(seed)

            (out_batch / f"{cid}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            per_case_results.append(result)

            # Aggregate round + adapter stats
            rounds = result.get("rounds") or []
            manifest["round_stats"]["rounds_total"] += len(rounds)
            sr = result.get("stop_reason", "")
            if sr in manifest["round_stats"]:
                manifest["round_stats"][f"stop_{sr}"] = \
                    manifest["round_stats"].get(f"stop_{sr}", 0) + 1
            for r in rounds:
                for a in (r.get("actions") or []):
                    t = a.get("tool") or ""
                    if t in manifest["adapter_call_count"]:
                        manifest["adapter_call_count"][t] += 1
                for ag in (r.get("agents") or []):
                    if ag in manifest["llm_call_count"]:
                        manifest["llm_call_count"][ag] += 1
            tp = result.get("trace_path", "")
            manifest["trace_coverage"]["with_trace" if tp and Path(tp).exists()
                                                  else "missing_trace"] += 1

            print(
                f"  [{result['source_batch']}] {cid}: "
                f"rounds={len(rounds)} stop={sr} elapsed={result['elapsed_s']}s",
            )

    # ---- Aggregate ----
    manifest["fresh_run_gate"] = (
        "pass" if (manifest["round_stats"]["rounds_total"] > 0
                   and manifest["trace_coverage"]["with_trace"] == len(per_case_results))
        else "fail"
    )

    # Write manifest + summary
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Reflection stats: per round-type counts
    ref_stats = {
        "by_stop_reason": {},
        "by_round_count": {},
        "url_repair_total": 0,
        "query_repair_total": 0,
        "placeholder_dropped_total": 0,
        "empty_url_repaired_total": 0,
        "noise_candidate_total": 0,
    }
    for c in per_case_results:
        sr = c.get("stop_reason", "unknown")
        ref_stats["by_stop_reason"][sr] = ref_stats["by_stop_reason"].get(sr, 0) + 1
        n = len(c.get("rounds") or [])
        ref_stats["by_round_count"][n] = ref_stats["by_round_count"].get(n, 0) + 1
        for r in (c.get("rounds") or []):
            ref_stats["url_repair_total"] += r.get("url_repair_n", 0)
            ref_stats["query_repair_total"] += r.get("query_repair_n", 0)
            ref_stats["placeholder_dropped_total"] += len(
                r.get("observations", {}).get("query_placeholder_leaks", []) or []
            )
    (out_dir / "reflection_stats.json").write_text(
        json.dumps(ref_stats, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Summary (machine readable)
    summary = {
        "audit_version": "Re10-reflection",
        "run_id": run_id,
        "n_total": len(per_case_results),
        "by_stop_reason": ref_stats["by_stop_reason"],
        "by_round_count": ref_stats["by_round_count"],
        "url_repair_total": ref_stats["url_repair_total"],
        "query_repair_total": ref_stats["query_repair_total"],
        "trace_coverage": manifest["trace_coverage"],
        "fresh_run_gate": manifest["fresh_run_gate"],
        "per_case": [{
            "case_id": c["case_id"],
            "title": c.get("title"),
            "stop_reason": c.get("stop_reason"),
            "rounds": len(c.get("rounds") or []),
            "seed_n": c.get("seed_n"),
            "elapsed_s": c.get("elapsed_s"),
            "trace_path": c.get("trace_path"),
        } for c in per_case_results],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"\n=== Re10 reflection done ({run_id}) ===")
    print(f"  by_stop_reason: {ref_stats['by_stop_reason']}")
    print(f"  by_round_count: {ref_stats['by_round_count']}")
    print(f"  url_repair_total: {ref_stats['url_repair_total']}")
    print(f"  query_repair_total: {ref_stats['query_repair_total']}")
    print(f"  trace_coverage: {manifest['trace_coverage']}")
    print(f"  fresh_run_gate: {manifest['fresh_run_gate']}")
    print(f"\n  manifest:  {out_dir}/run_manifest.json")
    print(f"  summary:   {out_dir}/summary.json")
    print(f"  refstats:  {out_dir}/reflection_stats.json")
    return 0 if manifest["fresh_run_gate"] == "pass" else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="tmp_re04_eval/balanced40_re10_reflection")
    ap.add_argument("--ids-file", default=None, help="restrict to a subset of case ids")
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())