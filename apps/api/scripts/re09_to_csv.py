"""Generate Re09 Balanced40 CSVs (case-level + candidate-level)."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "apps" / "api"))
PLAN_DIR = ROOT / "Plan"
RE09_DIR = ROOT / "tmp_re04_eval" / "balanced40_re09_fresh"
CASE_CSV = PLAN_DIR / "PaperAgent_Re09_Balanced40_逐论文审计.csv"
CAND_CSV = PLAN_DIR / "PaperAgent_Re09_Balanced40_候选论文.csv"
CASE_COLUMNS = [
    "case_id", "title", "status", "re08_status",
    "availability_level", "evidence_strength_label", "gap_flags",
    "paper_n", "baseline_n", "parallel_n", "dataset_n", "repo_n",
    "topic_dataset_n", "proxy_dataset_n", "pretrain_dataset_n", "generic_dataset_n",
    "core_n", "effective_core_n",
    "effective_baseline_n", "effective_parallel_n",
    "quarantined_baseline_n", "quarantined_parallel_n", "quarantined_core_n",
    "critical_consistency_error_n", "metadata_mismatch_n", "off_topic_core_n",
    "verification_verified_n", "verification_repaired_n",
    "verification_quarantined_n", "verification_not_found_n",
    "axis_status", "axis_missing_reasons",
    "evidence_gap_reasons", "notes",
    "fresh_new_candidates_n", "fresh_buckets",
    "fresh_elapsed_s", "adapter_count",
    "source_batch", "reason",
]
CAND_COLUMNS = [
    "case_id", "case_title", "source_batch", "priority",
    "bucket", "candidate_id", "title",
    "verification_status", "topic_relation", "recommended_action",
    "matched_keywords", "missing_keywords", "reason",
    "url", "doi", "year", "venue", "authors",
    "source_type", "repair_query", "repair_source",
]
def _availability_level(c):
    st = c.get("status")
    if st == "pass": return "ready"
    if st == "weak": return "needs_supplement"
    if st == "fail": return "blocked"
    return st or "unknown"
def _evidence_strength_label(c):
    n_aligned = (c.get("verification_verified_n") or 0)
    n_repaired = (c.get("verification_repaired_n") or 0)
    n_quarantined = (c.get("verification_quarantined_n") or 0)
    total = n_aligned + n_repaired + n_quarantined
    if total == 0: return "no_evidence"
    if n_quarantined > n_aligned + n_repaired: return "low"
    if n_aligned + n_repaired >= 5: return "high"
    if n_aligned + n_repaired >= 2: return "medium"
    return "low"
def _gap_flags(c):
    flags = []
    if c.get("topic_dataset_n", 0) == 0 and c.get("dataset_n", 0) > 0:
        flags.append("topic_dataset_missing")
    if c.get("effective_core_n", 0) == 0:
        flags.append("no_effective_core")
    if c.get("quarantined_baseline_n", 0) > 0:
        flags.append("quarantined_baseline")
    for r in (c.get("axis_missing_reasons") or []):
        flags.append(r)
    return ";".join(flags)
def _emit_case_csv(per_case):
    CASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CASE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CASE_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for c in per_case:
            row = {col: c.get(col, "") for col in CASE_COLUMNS}
            for k in ("axis_missing_reasons", "evidence_gap_reasons", "notes"):
                if isinstance(row.get(k), list):
                    row[k] = ";".join(str(x) for x in row[k])
            row["availability_level"] = _availability_level(c)
            row["evidence_strength_label"] = _evidence_strength_label(c)
            row["gap_flags"] = _gap_flags(c)
            if isinstance(row.get("fresh_buckets"), dict):
                row["fresh_buckets"] = ";".join(
                    f"{k}={v}" for k, v in row["fresh_buckets"].items())
            if isinstance(row.get("adapter_count"), dict):
                row["adapter_count"] = ";".join(
                    f"{k}={v}" for k, v in row["adapter_count"].items())
            w.writerow(row)
    return len(per_case)
def _emit_candidate_csv():
    rows = []
    if not RE09_DIR.exists(): return 0
    summary_path = RE09_DIR / "summary.json"
    if not summary_path.exists(): return 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    per_case_index = {c["case_id"]: c for c in (summary.get("per_case") or [])}
    for batch_dir in sorted(RE09_DIR.iterdir()):
        if not batch_dir.is_dir(): continue
        for case_path in sorted(batch_dir.glob("ENG-THESIS-*.json")):
            try:
                audit = json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            case_id = audit.get("case_id") or case_path.stem
            for nc in (audit.get("re09_fresh_repaired_candidates") or []):
                if not isinstance(nc, dict): continue
                rows.append({
                    "case_id": case_id,
                    "case_title": audit.get("title") or "",
                    "source_batch": audit.get("source_batch") or "re09_fresh",
                    "priority": audit.get("priority") or "",
                    "bucket": nc.get("repair_source") or "paper",
                    "candidate_id": nc.get("candidate_id") or "",
                    "title": nc.get("title") or "",
                    "verification_status": nc.get("verification_status") or "",
                    "topic_relation": nc.get("verification_topic_relation") or "",
                    "recommended_action": (
                        "keep" if (nc.get("verification_status") == "verified")
                        else "keep_as_proxy"),
                    "matched_keywords": "",
                    "missing_keywords": "",
                    "reason": audit.get("reason") or "",
                    "url": nc.get("url") or "",
                    "doi": nc.get("doi") or "",
                    "year": nc.get("year") or "",
                    "venue": nc.get("venue") or "",
                    "authors": (
                        ", ".join(nc.get("authors") or [])
                        if isinstance(nc.get("authors"), list)
                        else (nc.get("authors") or "")),
                    "source_type": nc.get("source_type") or nc.get("repair_source") or "",
                    "repair_query": nc.get("_query_origin") or "",
                    "repair_source": nc.get("repair_source") or "",
                })
    CAND_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CAND_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAND_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        rows.sort(key=lambda r: (
            {"core": 0, "baseline": 1, "parallel": 2, "dataset": 3, "repo": 4,
             "paper": 5}.get(r["bucket"], 6),
            r["case_id"], r["candidate_id"]))
        w.writerows(rows)
    return len(rows)
def main():
    summary_path = RE09_DIR / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found; run run_balanced40_fresh_re09.py first")
        return 1
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    per_case = data.get("per_case") or []
    n_case = _emit_case_csv(per_case)
    n_cand = _emit_candidate_csv()
    print(f"Wrote {n_case} rows to {CASE_CSV.name}  (case-level, {len(CASE_COLUMNS)} cols)")
    print(f"Wrote {n_cand} rows to {CAND_CSV.name}  (candidate-level, {len(CAND_COLUMNS)} cols)")
    print(f"  encoding: utf-8-sig (Excel-friendly)")
    return 0
if __name__ == "__main__":
    sys.exit(main())