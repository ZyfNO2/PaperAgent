"""Re04 SOP §5 Task 2 — Resource Retrieval Eval Harness.

Computes per-case `resource_status` and aggregate metrics from a
Re04 result dict. Used both offline (with a mocked client) and online
(LLM-online real LLM).

Acceptance per SOP §5 Task 2:
- Input = case title; call real run_research_agent_re04()
- Aggregate query_plan / candidate_pool / evidence_review /
  paper_groups / source_ledger
- Output per-case resource_status: pass | weak | fail | blocked
- No LLM self-evaluation
- No silent fail → adapter failure must surface in the report
- DO NOT use difficulty / cycle / repeatability

Status rules (SOP §4.2 + §4.3):
  pass       — paper >= 8 AND baseline >= 1 AND (repo OR dataset) >= 1
               AND no strong noise in core / baseline / parallel
  weak       — paper >= 4 AND baseline >= 1 AND no strong noise
  fail       — strong noise in core / baseline / parallel OR no baseline
  blocked    — needs_clarification OR LLM parse fail
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Strong-noise keyword set (cross-domain content the auditor can flag
# even without an LLM call). These are NOT used to FILTER — only to
# detect obviously cross-domain candidates that slipped into
# core / baseline / parallel.
STRONG_NOISE_TOKENS = (
    "astronomical", "galaxy", "AGN", "stellar", "astrophysics",
    "cosmic ray", "CERN", "Centauri", "star formation",
    "captcha", "carbohydrate", "pregnancy", "tumor in mouse",
    "twitter sentiment", "movie review", "bee movie", "fashion-mnist",
    "brown dwarf", "manga", "anime",
    "医学 CT", "肾肿瘤", "肺部", "脑部", "magnetic resonance",
    "手写汉字", "验证码",
    "Bogus", "Lorem ipsum",
)


def _is_strong_noise(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    for tok in STRONG_NOISE_TOKENS:
        if tok.lower() in t:
            return True
    return False


def _count_paper_like(pool: dict | list) -> int:
    """Count items with evidence_type == 'paper' in a candidate pool."""
    if isinstance(pool, list):
        return sum(1 for c in pool if (c.get("evidence_type") or "paper") == "paper")
    if isinstance(pool, dict):
        return len(pool.get("paper") or []) + sum(
            len(v) for k, v in pool.items() if k not in ("paper", "dataset", "repo")
        )
    return 0


def _count_type(pool: dict | list, t: str) -> int:
    if isinstance(pool, list):
        return sum(1 for c in pool if c.get("evidence_type") == t)
    if isinstance(pool, dict):
        return len(pool.get(t) or [])
    return 0


def _extract_evidence_review(er: Any) -> list[dict]:
    """ER may be a list of dicts / dataclasses, a dict {tier: [cands]},
    an EvidenceReview object, or None. Normalize to a list of dicts.
    """
    if er is None:
        return []
    if isinstance(er, list):
        out: list[dict] = []
        for r in er:
            if isinstance(r, dict):
                out.append(r)
            elif hasattr(r, "to_dict"):
                out.append(r.to_dict())
            elif hasattr(r, "__dict__"):
                # dataclass-like
                out.append({k: v for k, v in r.__dict__.items()})
        return out
    if isinstance(er, dict):
        out2: list[dict] = []
        for v in er.values():
            if isinstance(v, list):
                out2.extend(x.to_dict() if hasattr(x, "to_dict") else
                            (x if isinstance(x, dict) else
                             {k: val for k, val in x.__dict__.items()}))
            elif isinstance(v, dict):
                out2.append(v)
            elif hasattr(v, "to_dict"):
                out2.append(v.to_dict())
        return out2
    # EvidenceReview-like object with .reviews attribute or as_list()
    if hasattr(er, "reviews"):
        revs = er.reviews
        if isinstance(revs, list):
            return _extract_evidence_review(revs)
    if hasattr(er, "as_list"):
        revs = er.as_list()
        if isinstance(revs, list):
            return _extract_evidence_review(revs)
    if hasattr(er, "to_dict"):
        return [er.to_dict()]
    return []


def compute_resource_status(result: dict) -> dict[str, Any]:
    """Compute per-case resource_status from a Re04 result.

    Returns a dict with: status, paper_n, dataset_n, repo_n, baseline_n,
    parallel_n, has_strong_noise_in_core, evidence_gap_reasons.
    """
    if result.get("blocked_reason") == "needs_clarification":
        return {
            "status": "blocked",
            "reason": "needs_clarification",
            "paper_n": 0, "dataset_n": 0, "repo_n": 0,
            "baseline_n": 0, "parallel_n": 0,
            "has_strong_noise_in_core": False,
            "evidence_gap_reasons": ["empty raw_topic or no parsed atoms"],
        }

    pool = result.get("candidate_pool")
    if hasattr(pool, "by_evidence_type"):
        paper_n = len(pool.by_evidence_type("paper"))
        dataset_n = len(pool.by_evidence_type("dataset"))
        repo_n = len(pool.by_evidence_type("repo"))
    elif hasattr(pool, "as_list"):
        # CandidatePool object — fall back to its list
        items = pool.as_list()
        paper_n = _count_paper_like(items)
        dataset_n = _count_type(items, "dataset")
        repo_n = _count_type(items, "repo")
    elif isinstance(pool, list):
        paper_n = _count_paper_like(pool)
        dataset_n = _count_type(pool, "dataset")
        repo_n = _count_type(pool, "repo")
    elif isinstance(pool, dict):
        paper_n = _count_paper_like(pool)
        dataset_n = _count_type(pool, "dataset")
        repo_n = _count_type(pool, "repo")
    else:
        paper_n = dataset_n = repo_n = 0

    synthesis = result.get("synthesis") or {}
    paper_groups = (synthesis.get("paper_groups") or {}) if isinstance(synthesis, dict) else {}
    baseline_n = len(paper_groups.get("baseline") or [])
    parallel_n = len(paper_groups.get("parallel") or [])

    # Strong noise in core / baseline / parallel
    er = _extract_evidence_review(result.get("evidence_review"))
    core_titles: list[str] = []
    for r in er:
        if (r.get("status") or "").lower() == "core":
            core_titles.append(r.get("title") or r.get("paper_title") or "")
    candidate_pool = synthesis.get("candidate_pool") or {}
    for it in (candidate_pool.get("core") or []):
        core_titles.append(it.get("title") or "")
    for it in paper_groups.get("baseline") or []:
        core_titles.append(it.get("title") or "")
    for it in paper_groups.get("parallel") or []:
        core_titles.append(it.get("title") or "")
    has_noise = any(_is_strong_noise(t) for t in core_titles)

    evidence_gap_reasons: list[str] = []
    if paper_n < 8:
        evidence_gap_reasons.append(f"paper_n={paper_n} < 8")
    if baseline_n < 1:
        evidence_gap_reasons.append(f"baseline_n={baseline_n} < 1")
    if dataset_n + repo_n < 1:
        evidence_gap_reasons.append(f"dataset+repo={dataset_n + repo_n} < 1")

    # Decision matrix
    if has_noise:
        status = "fail"
        evidence_gap_reasons.append("strong_noise_in_core_or_baseline_or_parallel")
    elif baseline_n < 1:
        status = "fail"
    elif paper_n >= 8 and dataset_n + repo_n >= 1 and parallel_n >= 2:
        status = "pass"
    elif paper_n >= 4 and baseline_n >= 1:
        status = "weak"
    else:
        status = "fail"

    return {
        "status": status,
        "reason": ("; ".join(evidence_gap_reasons) if evidence_gap_reasons else "all_metrics_met"),
        "paper_n": paper_n,
        "dataset_n": dataset_n,
        "repo_n": repo_n,
        "baseline_n": baseline_n,
        "parallel_n": parallel_n,
        "has_strong_noise_in_core": has_noise,
        "evidence_gap_reasons": evidence_gap_reasons,
    }


def aggregate_metrics(per_case: list[dict]) -> dict[str, Any]:
    """Aggregate per-case status into SOP §4 metrics."""
    statuses = Counter(c.get("status") for c in per_case)
    total = sum(statuses.values()) or 1
    return {
        "total": sum(statuses.values()),
        "by_status": dict(statuses),
        "pass_rate": round((statuses.get("pass", 0) / total), 4),
        "weak_or_pass_rate": round(
            ((statuses.get("pass", 0) + statuses.get("weak", 0)) / total), 4,
        ),
        "fail_count": statuses.get("fail", 0),
        "blocked_count": statuses.get("blocked", 0),
        "strong_noise_cases": sum(1 for c in per_case if c.get("has_strong_noise_in_core")),
    }


def write_markdown_report(
    per_case: list[dict], out_path: str, *, source_url: str | None = None,
) -> None:
    """Write a human-readable per-case markdown report (SOP §7 #4)."""
    agg = aggregate_metrics(per_case)
    lines: list[str] = []
    lines.append("# Re04 Resource Retrieval Eval Report")
    lines.append("")
    if source_url:
        lines.append(f"Source JSONL: `{source_url}`")
        lines.append("")
    lines.append("## 整体统计 (Aggregate)")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| 总题数 | {agg['total']} |")
    lines.append(f"| pass | {agg['by_status'].get('pass', 0)} |")
    lines.append(f"| weak | {agg['by_status'].get('weak', 0)} |")
    lines.append(f"| fail | {agg['by_status'].get('fail', 0)} |")
    lines.append(f"| blocked | {agg['by_status'].get('blocked', 0)} |")
    lines.append(f"| pass_rate | {agg['pass_rate']:.1%} |")
    lines.append(f"| pass+weak_rate (SOP 合格线 ≥ 80%) | {agg['weak_or_pass_rate']:.1%} |")
    lines.append(f"| 强噪声 case 数 (SOP 上限 ≤ 1) | {agg['strong_noise_cases']} |")
    lines.append("")
    lines.append("## 每题 (Per-case)")
    lines.append("")
    lines.append("| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|---|")
    for c in per_case:
        lines.append("| {cid} | {title} | {st} | {pp} | {ds} | {rp} | {bl} | {pl} | {ns} | {rs} |".format(
            cid=c.get("case_id", "?"),
            title=(c.get("title") or "")[:40],
            st=c.get("status", "?"),
            pp=c.get("paper_n", 0),
            ds=c.get("dataset_n", 0),
            rp=c.get("repo_n", 0),
            bl=c.get("baseline_n", 0),
            pl=c.get("parallel_n", 0),
            ns="Y" if c.get("has_strong_noise_in_core") else "N",
            rs=(c.get("reason") or "")[:80],
        ))
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file; one record per non-empty line."""
    out: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out
