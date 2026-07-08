"""Generate Re08 Balanced40 CSVs.

  Plan/PaperAgent_Re08_Balanced40_逐论文审计.csv    case-level (40 rows)
  Plan/PaperAgent_Re08_Balanced40_候选论文.csv       candidate-level

Usage:
    PYTHONIOENCODING=utf-8 /g/PaperAgent/.venv/Scripts/python.exe \\
        G:/PaperAgent/apps/api/scripts/re08_to_csv.py
"""
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
RE08_DIR = ROOT / "tmp_re04_eval" / "balanced40_re08"
RE05_DIR = ROOT / "tmp_re04_eval" / "balanced40"

CASE_CSV = PLAN_DIR / "PaperAgent_Re08_Balanced40_逐论文审计.csv"
CAND_CSV = PLAN_DIR / "PaperAgent_Re08_Balanced40_候选论文.csv"

# Per Re08 SOP §6.1: every column listed MUST be populated and non-empty.
# score renamed to availability_level + gap_flags + evidence_strength_label.
CASE_COLUMNS = [
    "case_id", "title", "status", "availability_level",
    "evidence_strength_label", "gap_flags",
    "paper_n", "baseline_n", "parallel_n", "dataset_n", "repo_n",
    "topic_dataset_n", "proxy_dataset_n", "pretrain_dataset_n", "generic_dataset_n",
    "core_n", "effective_core_n",
    "effective_baseline_n", "effective_parallel_n",
    "quarantined_baseline_n", "quarantined_parallel_n", "quarantined_core_n",
    "critical_consistency_error_n", "metadata_mismatch_n", "off_topic_core_n",
    "verification_verified_n", "verification_repaired_n",
    "verification_quarantined_n", "verification_not_found_n",
    "axis_status", "axis_missing_reasons",
    "evidence_gap_reasons", "notes", "source_batch", "reason",
]

CAND_COLUMNS = [
    "case_id", "case_title", "source_batch",
    "bucket", "candidate_id", "title",
    "verification_status", "topic_relation", "recommended_action",
    "matched_keywords", "missing_keywords", "reason",
    "url", "doi", "year", "venue", "authors",
]


def _availability_level(c: dict) -> str:
    st = c.get("status")
    if st == "pass":
        return "ready"
    if st == "weak":
        return "needs_supplement"
    if st == "fail":
        return "blocked"
    return st or "unknown"


def _evidence_strength_label(c: dict) -> str:
    """Coarse evidence-strength tag derived from raw counts.  NOT a score."""
    n_aligned = (c.get("verification_verified_n") or 0)
    n_quarantined = (c.get("verification_quarantined_n") or 0)
    n_total = n_aligned + n_quarantined + (c.get("verification_repaired_n") or 0) \
        + (c.get("verification_not_found_n") or 0)
    if n_total == 0:
        return "no_evidence"
    if n_quarantined > n_aligned:
        return "low"
    if n_aligned >= 5:
        return "high"
    if n_aligned >= 2:
        return "medium"
    return "low"


def _gap_flags(c: dict) -> str:
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


def _index_re05_candidates() -> dict[str, dict]:
    index: dict[str, dict] = {}
    if not RE05_DIR.exists():
        return index
    for batch_dir in sorted(RE05_DIR.iterdir()):
        if not batch_dir.is_dir():
            continue
        for case_path in sorted(batch_dir.glob("ENG-THESIS-*.json")):
            try:
                dump = json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            synthesis = dump.get("synthesis") or {}
            candidate_pool = synthesis.get("candidate_pool") or {}
            paper_groups = synthesis.get("paper_groups") or {}

            def _absorb(items, role):
                if not isinstance(items, list):
                    return
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    cid = it.get("candidate_id") or it.get("id")
                    if not cid:
                        continue
                    new_meta = {
                        "title": it.get("title") or it.get("name") or "",
                        "url": it.get("url") or it.get("source_url") or "",
                        "doi": it.get("doi") or "",
                        "year": it.get("year") or "",
                        "venue": it.get("venue") or "",
                        "authors": (
                            ", ".join(it.get("authors") or [])
                            if isinstance(it.get("authors"), list)
                            else (it.get("authors") or "")
                        ),
                        "role_in_paper_groups": role,
                    }
                    if cid in index:
                        for k, v in new_meta.items():
                            if v and not index[cid].get(k):
                                index[cid][k] = v
                        continue
                    index[cid] = new_meta

            for bucket in ("core", "dataset", "repo"):
                _absorb(candidate_pool.get(bucket) or [], bucket)
            for pg_role in ("baseline", "parallel", "reference",
                             "long_tail_candidates"):
                _absorb(paper_groups.get(pg_role) or [], pg_role)
    return index


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
            w.writerow(row)
    return len(per_case)


def _emit_candidate_csv(re05_index):
    rows: list[dict] = []
    if not RE08_DIR.exists():
        return 0
    for batch_dir in sorted(RE08_DIR.iterdir()):
        if not batch_dir.is_dir():
            continue
        for case_path in sorted(batch_dir.glob("ENG-THESIS-*.json")):
            try:
                audit = json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            case_id = audit.get("case_id") or case_path.stem
            case_title = audit.get("title") or ""
            source_batch = audit.get("source_batch") or batch_dir.name
            records = audit.get("verification_records") or []
            for r in records:
                if not isinstance(r, dict):
                    continue
                cid = r.get("candidate_id") or ""
                meta = re05_index.get(cid, {})
                rows.append({
                    "case_id": case_id,
                    "case_title": case_title,
                    "source_batch": source_batch,
                    "bucket": r.get("bucket") or "",
                    "candidate_id": cid,
                    "title": meta.get("title") or "",
                    "verification_status": r.get("verification_status") or "",
                    "topic_relation": r.get("topic_relation") or "",
                    "recommended_action": r.get("recommended_action") or "",
                    "matched_keywords": ";".join(r.get("matched_keywords") or []),
                    "missing_keywords": ";".join(r.get("missing_keywords") or []),
                    "reason": r.get("reason") or "",
                    "url": meta.get("url") or "",
                    "doi": meta.get("doi") or "",
                    "year": meta.get("year") or "",
                    "venue": meta.get("venue") or "",
                    "authors": meta.get("authors") or "",
                })
    CAND_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CAND_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAND_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        bucket_order = {b: i for i, b in enumerate(
            ["core", "baseline", "parallel", "dataset", "repo"])}
        rows.sort(key=lambda r: (r["case_id"],
                                  bucket_order.get(r["bucket"], 99),
                                  r["candidate_id"]))
        w.writerows(rows)
    return len(rows)


def main():
    summary_path = RE08_DIR / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found; run reclassify_balanced40_re08.py first")
        return 1
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    per_case = data.get("per_case") or []
    re05_index = _index_re05_candidates()
    n_case = _emit_case_csv(per_case)
    n_cand = _emit_candidate_csv(re05_index)
    print(f"Wrote {n_case} rows to {CASE_CSV.name}  (case-level, {len(CASE_COLUMNS)} cols)")
    print(f"Wrote {n_cand} rows to {CAND_CSV.name}  (candidate-level, {len(CAND_COLUMNS)} cols)")
    print("  encoding: utf-8-sig (Excel-friendly)")
    return 0


if __name__ == "__main__":
    sys.exit(main())