"""Re10 FIX-2 case-level CSV audit extractor.

Usage::

    .venv/Scripts/python.exe apps/api/scripts/re10_fix2_to_csv.py \
        --re10-dir tmp_re04_eval/re10_fix2_typical_cases \
        --out-csv Plan/PaperAgent_Re10_FIX-2_典型样例审计.csv \
        --out-md  Plan/PaperAgent_Re10_FIX-2_典型样例审计.md

Reads per-case trace JSONs + summary, derives evidence + validator-style
classification, and emits a CSV/MD with the SOP §8-mandated columns:

case_id, title, domain_route, stop_reason, evidence_status,
adapter_attempt_n, adapter_success_n, adapter_error_n,
provider_error_summary, provider_circuit_breaker,
new_candidates_n, accepted_candidates_n, accepted_titles,
rejected_noise_titles, query_placeholder_leaks,
chinese_query_leaks, fixed_unet_fallback_seen,
primary_failure_mode, trace_path
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _derive_evidence(case: dict, trace: dict) -> dict:
    actions: list[dict] = []
    observations: list[dict] = []
    for r in (trace.get("rounds") or []):
        actions.extend(r.get("actions") or [])
        obs = r.get("observations") or {}
        if obs:
            observations.append(obs)

    search_actions = [a for a in actions if a.get("type") == "search"]
    repair_query_actions = [a for a in actions if a.get("type") == "repair_query"]
    repair_url_actions = [a for a in actions if a.get("type") == "repair_url"]

    adapter_attempt_n = len(search_actions)
    adapter_success_n = sum(
        1 for a in search_actions if a.get("status") in ("success", "no_results")
    )
    adapter_error_n = sum(1 for a in search_actions if a.get("status") == "error")
    missing_client_n = sum(
        1 for a in search_actions
        if "missing client" in str(a.get("error") or "").lower()
    )

    new_candidates_n = sum(
        int(r.get("accepted_n") or 0)
        for r in (trace.get("rounds") or [])
    )

    query_placeholder_leaks: list[str] = []
    for obs in observations:
        query_placeholder_leaks.extend(obs.get("query_placeholder_leaks") or [])

    empty_url_n = sum(
        len(obs.get("empty_url_candidates") or []) for obs in observations
    )

    chinese_query_leaks: list[str] = [
        a.get("query") for a in search_actions
        if any(0x4E00 <= ord(c) <= 0x9FFF for c in (a.get("query") or ""))
    ]

    unet_fallback_seen = any(
        "u-net semantic segmentation github implementation" in str(a.get("query") or "").lower()
        or "u-net neural network" in str(a.get("query") or "").lower()
        for a in actions
    )

    error_summary: dict[str, int] = Counter()
    cb_per_tool: dict[str, list[str]] = {}
    for a in search_actions:
        if a.get("status") == "error":
            err = str(a.get("error") or "")
            low = err.lower()
            for token in ("openalex", "crossref", "arxiv", "github", "huggingface"):
                if token in low:
                    error_summary[token] += 1
        if a.get("fallback_tool"):
            cb_per_tool.setdefault(a.get("tool"), []).append(
                f"fb={a['fallback_tool']}"
            )

    return {
        "case_id": case.get("case_id"),
        "stop_reason": case.get("stop_reason", ""),
        "adapter_attempt_n": adapter_attempt_n,
        "adapter_success_n": adapter_success_n,
        "adapter_error_n": adapter_error_n,
        "missing_client_n": missing_client_n,
        "new_candidates_n": new_candidates_n,
        "accepted_candidates_n": new_candidates_n,
        "query_repair_n": len(repair_query_actions),
        "url_repair_n": sum(
            1 for a in repair_url_actions
            if a.get("status") in ("url_repaired", "verified")
            or a.get("result_count", 0) > 0
        ),
        "empty_url_n": empty_url_n,
        "query_placeholder_leaks": query_placeholder_leaks,
        "chinese_query_leaks": chinese_query_leaks,
        "fixed_unet_fallback_seen": unet_fallback_seen,
        "provider_error_summary": dict(error_summary),
        "provider_circuit_breaker": "; ".join(
            f"{t}: {','.join(cb)}" for t, cb in cb_per_tool.items()
        ) or "",
    }


def _classify(ev: dict) -> str:
    if ev.get("batch_repeated_accepted_title_n", 0) > 0:
        return "fail"
    if ev.get("topic_axis_pass_n", 0) == 0 and ev.get("new_candidates_n", 0) > 0:
        return "fail"
    if ev["missing_client_n"] > 0 or ev["adapter_success_n"] == 0:
        return "blocked_tooling"
    if ev["adapter_attempt_n"] == 0:
        return "blocked_tooling"
    if ev["new_candidates_n"] >= 1:
        return "pass"
    if ev["new_candidates_n"] == 0 and ev["accepted_candidates_n"] == 0:
        return "fail" if ev["adapter_attempt_n"] >= 2 else "weak"
    return "weak"


def _failure_mode(ev: dict, status: str) -> str:
    if status == "pass":
        return "OK"
    if ev["missing_client_n"] > 0:
        return f"missing_client_n={ev['missing_client_n']}"
    if ev["new_candidates_n"] == 0:
        return "no candidates surface (verify/post-filter)"
    if ev["adapter_attempt_n"] == 0:
        return "no adapter attempts"
    return "n/a"


def _accepted_titles(case: dict, trace: dict) -> list[str]:
    """Pull candidate titles from the per-case batch JSON's final_candidate_pool."""
    return [c["title"][:80] for c in _accepted_candidate_items(case, trace)]


def _accepted_candidate_items(case: dict, trace: dict) -> list[dict]:
    """Pull accepted candidates with verifier metadata from final_candidate_pool."""
    seen: set[str] = set()
    out: list[dict] = []
    batch_path = case.get("_batch_case_path") or (
        Path(case.get("trace_path", "")).parent.parent / case.get("source_batch", "batch1") / f"{case.get('case_id')}.json"
        if case.get("trace_path") else None
    )
    if batch_path and Path(str(batch_path)).exists():
        try:
            bj = json.loads(Path(str(batch_path)).read_text(encoding="utf-8"))
            pool = bj.get("final_candidate_pool") or []
            for c in pool if isinstance(pool, list) else []:
                if not isinstance(c, dict):
                    continue
                t = (c.get("title") or c.get("name") or c.get("full_name") or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    out.append({
                        "title": t,
                        "bucket": c.get("_bucket") or "",
                        "relation": c.get("verification_topic_relation") or "",
                        "matched": c.get("verification_matched_keywords") or [],
                        "related": c.get("verification_related_keywords") or [],
                    })
        except Exception:
            pass
    return out[:8]  # type: ignore[unreachable]  # noqa: ERA001


def _axis_stats(items: list[dict]) -> dict:
    axis_pass = 0
    paper_pass = 0
    repo_pass = 0
    dataset_pass = 0
    repo_only = 0
    for item in items:
        relation = item.get("relation")
        has_axis_hit = bool(item.get("matched") or item.get("related"))
        ok = relation in {"direct", "proxy"} and has_axis_hit
        if not ok:
            continue
        axis_pass += 1
        bucket = item.get("bucket") or "paper"
        if bucket == "repo":
            repo_pass += 1
        elif bucket == "dataset":
            dataset_pass += 1
        else:
            paper_pass += 1
    if axis_pass and axis_pass == repo_pass:
        repo_only = 1
    return {
        "topic_axis_pass_n": axis_pass,
        "paper_axis_pass_n": paper_pass,
        "dataset_axis_pass_n": dataset_pass,
        "repo_axis_pass_n": repo_pass,
        "repo_only_pass": repo_only,
    }


def _rejected_titles(case: dict) -> list[str]:
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--re10-dir", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()
    rd = Path(args.re10_dir)
    summary = json.loads((rd / "summary.json").read_text(encoding="utf-8"))
    cases = summary.get("per_case") or []
    if not cases:
        print("no cases", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for c in cases:
        cid = c["case_id"]
        tp = c.get("trace_path") or (rd / "traces" / f"{cid}.json")
        trace = json.loads(Path(tp).read_text(encoding="utf-8"))
        ev = _derive_evidence(c, trace)
        items = _accepted_candidate_items(c, trace)
        ev.update(_axis_stats(items))
        status = c.get("stop_reason", "")
        rows.append({
            "case_id": cid,
            "title": c.get("title", ""),
            "domain_route": "",
            "re10_status": status,
            "stop_reason": status,
            "evidence_status": "",
            "adapter_attempt_n": ev["adapter_attempt_n"],
            "adapter_success_n": ev["adapter_success_n"],
            "adapter_error_n": ev["adapter_error_n"],
            "missing_client_n": ev["missing_client_n"],
            "new_candidates_n": ev["new_candidates_n"],
            "accepted_candidates_n": ev["accepted_candidates_n"],
            "query_repair_n": ev["query_repair_n"],
            "url_repair_n": ev["url_repair_n"],
            "empty_url_n": ev["empty_url_n"],
            "topic_axis_pass_n": ev["topic_axis_pass_n"],
            "paper_axis_pass_n": ev["paper_axis_pass_n"],
            "dataset_axis_pass_n": ev["dataset_axis_pass_n"],
            "repo_axis_pass_n": ev["repo_axis_pass_n"],
            "repo_only_pass": ev["repo_only_pass"],
            "batch_repeated_accepted_title_n": 0,
            "batch_repeated_accepted_titles": "[]",
            "provider_error_summary": json.dumps(
                ev["provider_error_summary"], ensure_ascii=False,
            ),
            "provider_circuit_breaker": ev["provider_circuit_breaker"],
            "query_placeholder_leaks": json.dumps(
                ev["query_placeholder_leaks"], ensure_ascii=False,
            ),
            "chinese_query_leaks": json.dumps(
                ev["chinese_query_leaks"], ensure_ascii=False,
            ),
            "fixed_unet_fallback_seen": ev["fixed_unet_fallback_seen"],
            "primary_failure_mode": "",
            "accepted_titles": json.dumps(
                [item["title"][:80] for item in items], ensure_ascii=False,
            ),
            "rejected_noise_titles": json.dumps(
                _rejected_titles(c), ensure_ascii=False,
            ),
            "trace_path": str(Path(tp).resolve()),
        })

    title_counter: Counter[str] = Counter()
    for r in rows:
        for title in json.loads(r["accepted_titles"]):
            title_counter[str(title).strip().lower()] += 1
    repeated = {
        t for t, n in title_counter.items()
        if t and n >= 3
    }

    by_status = Counter()
    for r in rows:
        repeated_titles = [
            t for t in json.loads(r["accepted_titles"])
            if str(t).strip().lower() in repeated
        ]
        r["batch_repeated_accepted_title_n"] = len(repeated_titles)
        r["batch_repeated_accepted_titles"] = json.dumps(
            repeated_titles[:5], ensure_ascii=False,
        )
        ev_for_status = dict(r)
        ev_for_status["new_candidates_n"] = int(r["new_candidates_n"])
        ev_for_status["accepted_candidates_n"] = int(r["accepted_candidates_n"])
        ev_for_status["adapter_attempt_n"] = int(r["adapter_attempt_n"])
        ev_for_status["adapter_success_n"] = int(r["adapter_success_n"])
        ev_for_status["missing_client_n"] = int(r["missing_client_n"])
        ev_for_status["topic_axis_pass_n"] = int(r["topic_axis_pass_n"])
        ev_for_status["batch_repeated_accepted_title_n"] = int(
            r["batch_repeated_accepted_title_n"]
        )
        est = _classify(ev_for_status)
        r["evidence_status"] = est
        r["primary_failure_mode"] = _failure_mode(ev_for_status, r["stop_reason"])
        if r["batch_repeated_accepted_title_n"]:
            r["primary_failure_mode"] = "batch repeated accepted title pollution"
        elif r["topic_axis_pass_n"] == 0 and r["new_candidates_n"]:
            r["primary_failure_mode"] = "accepted candidates lack topic-axis match"
        by_status[est] += 1

    cols = [
        "case_id", "title", "domain_route", "re10_status", "stop_reason",
        "evidence_status", "adapter_attempt_n", "adapter_success_n",
        "adapter_error_n", "missing_client_n", "new_candidates_n",
        "accepted_candidates_n", "query_repair_n", "url_repair_n",
        "empty_url_n", "topic_axis_pass_n", "paper_axis_pass_n",
        "dataset_axis_pass_n", "repo_axis_pass_n", "repo_only_pass",
        "batch_repeated_accepted_title_n", "batch_repeated_accepted_titles",
        "provider_error_summary",
        "provider_circuit_breaker", "query_placeholder_leaks",
        "chinese_query_leaks", "fixed_unet_fallback_seen",
        "primary_failure_mode", "accepted_titles",
        "rejected_noise_titles", "trace_path",
    ]
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("# Re10 FIX-2 case-level audit\n\n")
        f.write(f"data_source: `{rd}`\n\n")
        f.write(f"n_cases: {len(rows)}\n\n")
        f.write(f"by_status: {dict(by_status)}\n\n")
        f.write("| " + " | ".join([
            "case_id", "title", "stop", "status", "attempt", "success",
            "error", "new", "accepted", "provider_error", "primary_failure",
        ]) + " |\n")
        f.write("| " + " | ".join(["---"] * 11) + " |\n")
        for r in rows:
            f.write(
                f"| {r['case_id']} | {r['title'][:40]} | {r['stop_reason']} | "
                f"{r['evidence_status']} | {r['adapter_attempt_n']} | "
                f"{r['adapter_success_n']} | {r['adapter_error_n']} | "
                f"{r['new_candidates_n']} | {r['accepted_candidates_n']} | "
                f"{r['provider_error_summary']} | {r['primary_failure_mode']} |\n"
            )
        f.write("\n## accepted_titles (first 3 per case)\n\n")
        for r in rows:
            titles = json.loads(r["accepted_titles"])
            f.write(f"### {r['case_id']} - {r['title']}\n")
            for t in titles[:3]:
                f.write(f"- {t}\n")
            f.write("\n")
    print(f"wrote {args.out_csv} + {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
