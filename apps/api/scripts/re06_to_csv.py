"""Generate TWO CSVs for the Re06 Balanced40 report:

  1. PaperAgent_Re06_Balanced40_逐论文审计.csv      (case-level: 40 rows)
  2. PaperAgent_Re06_Balanced40_候选论文.csv          (candidate-level: one
     row per individual paper / dataset / repo that landed in any
     bucket, with its case_id + bucket + role + audit result +
     original URL / abstract snippet from the Re05 raw dump).

The candidate-level CSV joins two sources:
  * ``tmp_re04_eval/balanced40_re06/<batch>/<case>.json`` — Re06
    audit dump; carries ``bucket_audit.<bucket>.members[]`` with
    ``candidate_id`` / ``consistency_status`` / ``axis_coverage`` /
    ``evidence_quality`` / ``decision_reason``.
  * ``tmp_re04_eval/balanced40/<batch>/<case>.json`` — Re05 LLM-
    online raw dump; carries ``synthesis.candidate_pool.{core,...}``
    and ``synthesis.paper_groups.{baseline,parallel,...}`` with the
    actual ``url`` / ``abstract`` / ``source_type`` for each
    candidate.

We match by ``candidate_id``; if the candidate lacks an id, we fall
back to (case_id, bucket, title) tuple.

Encoding: utf-8-sig so Excel opens without garbled CJK.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
        apps/api/scripts/re06_to_csv.py
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
RE06_DIR = ROOT / "tmp_re04_eval" / "balanced40_re06"
RE05_DIR = ROOT / "tmp_re04_eval" / "balanced40"
SUMMARY_JSON = RE06_DIR / "summary.json"

CASE_CSV = PLAN_DIR / "PaperAgent_Re06_Balanced40_逐论文审计.csv"
CAND_CSV = PLAN_DIR / "PaperAgent_Re06_Balanced40_候选论文.csv"

CASE_COLUMNS = [
    "case_id", "title", "status",
    "paper_n", "baseline_n", "parallel_n", "dataset_n", "repo_n",
    "topic_dataset_n", "proxy_dataset_n", "pretrain_dataset_n", "generic_dataset_n",
    "core_direct_n", "baseline_direct_n", "baseline_proxy_n",
    "parallel_direct_n", "parallel_proxy_n",
    "critical_consistency_error_n", "metadata_mismatch_n", "off_topic_core_n",
    "axis_missing_reasons", "source_batch", "reason",
]

CAND_COLUMNS = [
    "case_id", "case_title", "source_batch",
    "bucket",                    # core | baseline | parallel | dataset | repo
    "candidate_id", "title", "title_zh",
    "url", "doi",
    "source_type", "year", "venue", "authors",
    "abstract_snippet",
    "consistency_status",        # aligned | proxy | generic | metadata_mismatch | off_topic | insufficient_metadata
    "axis_task", "axis_object", "axis_method", "axis_scenario",
    "evidence_has_title", "evidence_has_abstract", "evidence_has_url",
    "evidence_title_abstract_consistent",
    "decision_reason",
    "role_in_paper_groups",      # baseline | parallel | reference | long_tail
]


# ---------------------------------------------------------------------------
# Step 1 — read Re05 raw dump and build a candidate metadata index
# ---------------------------------------------------------------------------

def _index_re05_candidates() -> dict[str, dict]:
    """Return ``{candidate_id: meta_dict}`` from every Re05 raw dump.

    Re04/05 candidates may live in:
      * ``synthesis.candidate_pool.{core,dataset,repo}``     (per-bucket list)
      * ``synthesis.paper_groups.{baseline,parallel,reference,
        long_tail_candidates}``                              (LLM ER buckets)
      * ``candidate_pool`` top-level list                    (raw pool)

    Each candidate carries ``candidate_id`` (e.g. ``c-a3d8365f``)
    and may carry ``url`` / ``doi`` / ``source_type`` /
    ``abstract`` / ``year`` / ``venue`` / ``authors`` /
    ``relation_to_topic`` (used to derive ``role_in_paper_groups``).
    """
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

            def _absorb(items: list, role_in_paper_groups: str) -> None:
                """Merge candidate metadata; later absorbs fill missing fields
                without overwriting already-present ones.

                This lets the top-level ``candidate_pool`` list (which
                carries the real ``url`` / ``abstract`` / ``year`` /
                ``venue`` / ``authors``) enrich the LLM-bucket entries
                that only carry ``candidate_id`` + ``title``.
                """
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
                        "role_in_paper_groups": role_in_paper_groups,
                    }
                    if cid in index:
                        # Merge: keep first non-empty value for each field.
                        for k, v in new_meta.items():
                            if v and not index[cid].get(k):
                                index[cid][k] = v
                        continue
                    index[cid] = new_meta

            # IMPORTANT: absorb order matters.  Top-level pool first
            # (has the rich url/abstract fields); then LLM buckets
            # fill in any missing fields.
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


# ---------------------------------------------------------------------------
# Step 2 — emit case-level CSV
# ---------------------------------------------------------------------------

def _emit_case_csv(per_case: list[dict]) -> int:
    CASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CASE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CASE_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for c in per_case:
            row = {col: c.get(col, "") for col in CASE_COLUMNS}
            if isinstance(row.get("axis_missing_reasons"), list):
                row["axis_missing_reasons"] = ";".join(row["axis_missing_reasons"])
            w.writerow(row)
    return len(per_case)


# ---------------------------------------------------------------------------
# Step 3 — emit candidate-level CSV (joins Re06 audit + Re05 metadata)
# ---------------------------------------------------------------------------

def _emit_candidate_csv(re05_index: dict[str, dict]) -> int:
    """Emit one row per audit_dump.bucket_audit member.

    Members now carry the candidate's url / abstract / source_type /
    year / venue / authors directly (added in evidence_consistency.py
    ``_record``).  We still keep a Re05 fallback for backward compat
    with audit dumps written before that change.
    """
    rows: list[dict] = []
    if not RE06_DIR.exists():
        return 0
    for batch_dir in sorted(RE06_DIR.iterdir()):
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
                members = bucket.get("members") or []
                for m in members:
                    if not isinstance(m, dict):
                        continue
                    cid = m.get("candidate_id") or ""
                    # Prefer member fields (Re06 audit dump).  Fall
                    # back to Re05 raw dump index for any field still
                    # missing (older dumps pre-_record change).
                    meta = re05_index.get(cid, {})
                    ax = m.get("axis_coverage") or {}
                    q = m.get("evidence_quality") or {}
                    def _field(*names: str) -> str:
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
                        "title_zh": "",
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
                        "role_in_paper_groups": _field("role_in_paper_groups", "relation_to_topic"),
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


def main() -> int:
    if not SUMMARY_JSON.exists():
        print(f"ERROR: {SUMMARY_JSON} not found; run reclassify_balanced40.py first")
        return 1
    data = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    per_case = data.get("per_case") or []
    re05_index = _index_re05_candidates()
    n_case = _emit_case_csv(per_case)
    n_cand = _emit_candidate_csv(re05_index)
    print(f"Wrote {n_case} rows to {CASE_CSV.name}  (case-level, {len(CASE_COLUMNS)} cols)")
    print(f"Wrote {n_cand} rows to {CAND_CSV.name}  "
          f"(candidate-level, {len(CAND_COLUMNS)} cols)")
    print("  encoding: utf-8-sig (Excel-friendly)")
    print(f"  re05 candidate index: {len(re05_index)} unique ids")
    return 0


if __name__ == "__main__":
    sys.exit(main())