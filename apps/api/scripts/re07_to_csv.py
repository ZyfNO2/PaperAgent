"""Generate two CSVs for the Re07 Balanced40 report.

  1. Plan/PaperAgent_Re07_Balanced40_逐论文审计.csv     (case-level: 40 rows)
  2. Plan/PaperAgent_Re07_Balanced40_候选论文.csv         (candidate-level)

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
        apps/api/scripts/re07_to_csv.py
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
RE07_DIR = ROOT / "tmp_re04_eval" / "balanced40_re07"
RE05_DIR = ROOT / "tmp_re04_eval" / "balanced40"
SUMMARY_JSON = RE07_DIR / "summary.json"

CASE_CSV = PLAN_DIR / "PaperAgent_Re07_Balanced40_逐论文审计.csv"
CAND_CSV = PLAN_DIR / "PaperAgent_Re07_Balanced40_候选论文.csv"

CASE_COLUMNS = [
    "case_id", "title", "status", "score",
    "paper_n", "baseline_n", "parallel_n", "dataset_n", "repo_n",
    "topic_dataset_n", "proxy_dataset_n", "pretrain_dataset_n", "generic_dataset_n",
    "core_n", "effective_core_n",
    "effective_baseline_n", "effective_parallel_n",
    "quarantined_baseline_n", "quarantined_parallel_n", "quarantined_core_n",
    "critical_consistency_error_n", "metadata_mismatch_n", "off_topic_core_n",
    "axis_status", "notes", "source_batch", "reason",
]

CAND_COLUMNS = [
    "case_id", "case_title", "source_batch",
    "bucket", "candidate_id", "title",
    "url", "doi", "source_type", "year", "venue", "authors",
    "abstract_snippet",
    "consistency_status",
    "axis_task", "axis_object", "axis_method", "axis_scenario",
    "evidence_has_title", "evidence_has_abstract", "evidence_has_url",
    "evidence_title_abstract_consistent",
    "decision_reason", "role_in_paper_groups",
]


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
                        "source_type": (
                            it.get("source_type") or it.get("source") or ""
                        ),
                        "year": it.get("year") or "",
                        "venue": it.get("venue") or "",
                        "authors": (
                            ", ".join(it.get("authors") or [])
                            if isinstance(it.get("authors"), list)
                            else (it.get("authors") or "")
                        ),
                        "abstract_snippet":
                            (it.get("abstract") or it.get("snippet") or "")[:300],
                        "relation_to_topic": it.get("relation_to_topic") or "",
                        "role_in_paper_groups": role,
                    }
                    if cid in index:
                        for k, v in new_meta.items():
                            if v and not index[cid].get(k):
                                index[cid][k] = v
                        continue
                    index[cid] = new_meta

            top_pool = dump.get("candidate_pool")
            if isinstance(top_pool, list):
                _absorb(top_pool, "")
            for bucket in ("core", "dataset", "repo"):
                _absorb(candidate_pool.get(bucket) or [], bucket)
            for pg_role in ("baseline", "parallel", "reference",
                             "long_tail_candidates"):
                _absorb(paper_groups.get(pg_role) or [], pg_role)
            _absorb(candidate_pool.get("long_tail_candidates") or [],
                     "long_tail_candidates")
    return index


def _emit_case_csv(per_case):
    CASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CASE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CASE_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for c in per_case:
            row = {col: c.get(col, "") for col in CASE_COLUMNS}
            if isinstance(row.get("notes"), list):
                row["notes"] = ";".join(row["notes"])
            w.writerow(row)
    return len(per_case)


def _emit_candidate_csv(re05_index):
    rows = []
    if not RE07_DIR.exists():
        return 0
    for batch_dir in sorted(RE07_DIR.iterdir()):
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
            bucket_audit = audit.get("bucket_audit") or {}
            for bucket_name, bucket in bucket_audit.items():
                for m in (bucket.get("members") or []):
                    if not isinstance(m, dict):
                        continue
                    cid = m.get("candidate_id") or ""
                    meta = re05_index.get(cid, {})
                    ax = m.get("axis_coverage") or {}
                    q = m.get("evidence_quality") or {}
                    def _field(*names):
                        for n in names:
                            v = m.get(n)
                            if v:
                                return v
                            v = meta.get(n)
                            if v:
                                return v
                        return ""
                    rows.append({
                        "case_id": case_id,
                        "case_title": case_title,
                        "source_batch": source_batch,
                        "bucket": bucket_name,
                        "candidate_id": cid,
                        "title": m.get("title") or meta.get("title") or "",
                        "url": _field("url"),
                        "doi": _field("doi"),
                        "source_type": _field("source_type", "source"),
                        "year": _field("year"),
                        "venue": _field("venue"),
                        "authors": _field("authors"),
                        "abstract_snippet": _field("abstract_snippet", "abstract"),
                        "consistency_status": m.get("consistency_status") or "",
                        "axis_task": ax.get("task") or "",
                        "axis_object": ax.get("object") or "",
                        "axis_method": ax.get("method") or "",
                        "axis_scenario": ax.get("scenario") or "",
                        "evidence_has_title": q.get("has_title", ""),
                        "evidence_has_abstract": q.get("has_abstract", ""),
                        "evidence_has_url": q.get("has_url", ""),
                        "evidence_title_abstract_consistent":
                            q.get("title_abstract_consistent", ""),
                        "decision_reason": m.get("decision_reason") or "",
                        "role_in_paper_groups": _field(
                            "role_in_paper_groups", "relation_to_topic"
                        ),
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
    if not SUMMARY_JSON.exists():
        print(f"ERROR: {SUMMARY_JSON} not found; run reclassify_balanced40.py first")
        return 1
    data = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
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