"""Re06 — Evidence Consistency Auditor.

Replaces Re04's ``STRONG_NOISE_TOKENS`` keyword blacklist with a
structured, per-candidate consistency audit.

For each candidate, the auditor computes:
  * ``consistency_status``: aligned | proxy | generic |
    metadata_mismatch | off_topic | insufficient_metadata
  * ``axis_coverage``: per-axis (task / object / method / scenario)
    direct | proxy | missing
  * ``evidence_quality``: has_title / has_abstract / has_url /
    source_type / title_abstract_consistent

The auditor is **rule-based**: it never hits the network, never
calls an LLM, never modifies the candidate pool, and never references
any local hardcoded domain blocklist.  When the rule audit returns
``insufficient_metadata``, the caller may invoke the LLM reviewer
defined in ``prompts/evidence_consistency_review.md`` for a second
opinion (also non-network-bound — pure prompt contract).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any


# Common English / Chinese stopwords used when computing word overlap
# between title and abstract.  Purely a tokenization aid — not a
# blacklist.  Kept short on purpose.
_STOPWORDS = frozenset(
    "a an the of and or for to in on with by from is are be as at "
    "this that these those it its into over under between through "
    "based using use used approach method study paper research work "
    "new novel improved effective efficient robust automatic "
    "一种 基于 研究 方法 分析 检测 识别 模型 算法 网络 深度 学习 "
    "图像 处理 系统 设计 实现 改进 优化 性能 实验 结果 验证"
    .split()
)


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    text = text.lower()
    # split on non-word; keep CJK characters as whole runs
    text = re.sub(r"[^\w\s一-鿿-]", " ", text, flags=re.UNICODE)
    tokens = {t for t in text.split() if len(t) >= 2}
    return {t for t in tokens if t not in _STOPWORDS}


@dataclass
class AxisCoverage:
    task: str = "missing"       # direct | proxy | missing
    object: str = "missing"
    method: str = "missing"
    scenario: str = "missing"


@dataclass
class EvidenceQuality:
    has_title: bool = False
    has_abstract: bool = False
    has_url: bool = False
    source_type: str = "unknown"
    title_abstract_consistent: bool = True


@dataclass
class ConsistencyResult:
    candidate_id: str
    role: str
    consistency_status: str
    axis_coverage: AxisCoverage = field(default_factory=AxisCoverage)
    evidence_quality: EvidenceQuality = field(default_factory=EvidenceQuality)
    decision_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _axis_match(
    topic_atoms: dict[str, list[str]] | None, axis: str, haystack: str,
) -> str:
    """Compute axis coverage for one axis name.

    Returns ``direct`` / ``proxy`` / ``missing``.
    """
    if not topic_atoms or not haystack:
        return "missing"
    atoms = [a.lower() for a in (topic_atoms.get(axis) or []) if a]
    if not atoms:
        return "missing"
    hs = haystack.lower()
    direct_hits = [a for a in atoms if a in hs]
    if direct_hits:
        return "direct"
    # Proxy: any single token >= 4 chars from atom appears as substring
    proxy_hits = [a for a in atoms if any(len(t) >= 4 and t in hs for t in a.split())]
    if proxy_hits:
        return "proxy"
    return "missing"


def _title_abstract_consistent(
    title: str, abstract: str,
) -> bool:
    """Check whether title and abstract are about the same paper.

    Heuristic: compute Jaccard overlap on tokenized title and abstract.
    If overlap is below a low floor (0.05) AND both contain distinct
    high-information tokens, flag as inconsistent.
    """
    if not title or not abstract:
        return True   # cannot disprove consistency from silence
    title_tokens = _tokenize(title)
    abstract_tokens = _tokenize(abstract)
    if not title_tokens or not abstract_tokens:
        return True
    overlap = len(title_tokens & abstract_tokens)
    union = len(title_tokens | abstract_tokens) or 1
    jaccard = overlap / union
    # title tokens should mostly appear in abstract
    title_coverage = overlap / max(len(title_tokens), 1)
    if jaccard < 0.05 and title_coverage < 0.20:
        return False
    return True


def audit_candidate(
    candidate: dict[str, Any],
    *,
    role: str,
    topic_atoms: dict[str, list[str]] | None = None,
    meta: dict[str, Any] | None = None,
) -> ConsistencyResult:
    """Audit a single candidate.

    Parameters
    ----------
    candidate
        Must have at least ``title``.  Optional: ``candidate_id``,
        ``abstract``/``snippet``, ``url``, ``source_type``/``source``.
    role
        Proposed role (``core`` / ``baseline`` / ``parallel`` /
        ``dataset`` / ``repo`` / ``rejected``).
    topic_atoms
        Topic atoms shaped ``{"task": [...], "object": [...], "method": [...], "scenario": [...]}``.
    meta
        Optional rich-metadata dict (typically the top-level pool
        entry for the same candidate_id).  Used to populate the
        ``EvidenceQuality`` fields when the bucket-level candidate
        dict only carries ``candidate_id`` + ``title``.
    """
    # Merge meta into candidate for the fields that are missing.
    if meta:
        merged = dict(candidate)
        for k, v in meta.items():
            if v and not merged.get(k):
                merged[k] = v
        candidate = merged
    cid = candidate.get("candidate_id") or candidate.get("id") or "c-unknown"
    title = (candidate.get("title") or "").strip()
    abstract = (candidate.get("abstract") or candidate.get("snippet") or "").strip()
    url = (candidate.get("url") or "").strip()
    src = (
        candidate.get("source_type")
        or candidate.get("source")
        or "unknown"
    ).strip() or "unknown"

    haystack = " ".join([title, abstract]).strip()

    # ---- Quality ----
    title_abs_consistent = _title_abstract_consistent(title, abstract) if abstract else True
    quality = EvidenceQuality(
        has_title=bool(title),
        has_abstract=bool(abstract),
        has_url=bool(url),
        source_type=src,
        title_abstract_consistent=title_abs_consistent,
    )

    # ---- Insufficient metadata ----
    if not title:
        return ConsistencyResult(
            candidate_id=cid,
            role=role,
            consistency_status="insufficient_metadata",
            axis_coverage=AxisCoverage(),
            evidence_quality=quality,
            decision_reason="candidate has no title — cannot audit",
        )

    # ---- Metadata mismatch ----
    if not title_abs_consistent:
        return ConsistencyResult(
            candidate_id=cid,
            role=role,
            consistency_status="metadata_mismatch",
            axis_coverage=AxisCoverage(),
            evidence_quality=quality,
            decision_reason=(
                "title and abstract share <5% tokens — likely two different "
                "papers glued together (e.g. crossref metadata mismatch)"
            ),
        )

    # ---- Axis coverage ----
    cov = AxisCoverage(
        task=_axis_match(topic_atoms, "task", haystack),
        object=_axis_match(topic_atoms, "object", haystack),
        method=_axis_match(topic_atoms, "method", haystack),
        scenario=_axis_match(topic_atoms, "scenario", haystack),
    )
    direct_axes = sum(1 for v in (cov.task, cov.object, cov.method, cov.scenario) if v == "direct")
    proxy_axes = sum(1 for v in (cov.task, cov.object, cov.method, cov.scenario) if v == "proxy")

    # ---- Status decision (rule-based, no blacklist) ----
    if direct_axes >= 2:
        status = "aligned"
        reason = f"{direct_axes}/4 axes directly match topic atoms"
    elif direct_axes == 1 and proxy_axes >= 1:
        status = "aligned"
        reason = f"1 direct + {proxy_axes} proxy axis — strong topical fit"
    elif direct_axes == 1:
        status = "proxy"
        reason = "1 axis directly matches — partial fit"
    elif proxy_axes >= 1:
        status = "proxy"
        reason = f"{proxy_axes}/4 axes proxy-match — adjacent topic"
    elif not topic_atoms:
        status = "insufficient_metadata"
        reason = "no topic atoms available for axis matching"
    else:
        # 0 direct, 0 proxy across all four axes — topic atoms miss
        # entirely.  This is the off_topic branch.
        status = "off_topic"
        reason = "no axis token matches the topic atoms"

    return ConsistencyResult(
        candidate_id=cid,
        role=role,
        consistency_status=status,
        axis_coverage=cov,
        evidence_quality=quality,
        decision_reason=reason,
    )


# ---------------------------------------------------------------------------
# Apply audit to a synthesis result and aggregate per-bucket counters
# ---------------------------------------------------------------------------

@dataclass
class BucketAudit:
    n_total: int = 0
    n_aligned: int = 0
    n_proxy: int = 0
    n_generic: int = 0
    n_metadata_mismatch: int = 0
    n_off_topic: int = 0
    n_insufficient: int = 0
    critical_consistency_error_n: int = 0    # metadata_mismatch + off_topic in core/baseline/parallel
    members: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "n_aligned": self.n_aligned,
            "n_proxy": self.n_proxy,
            "n_generic": self.n_generic,
            "n_metadata_mismatch": self.n_metadata_mismatch,
            "n_off_topic": self.n_off_topic,
            "n_insufficient": self.n_insufficient,
            "critical_consistency_error_n": self.critical_consistency_error_n,
            "members": self.members,
        }


def audit_synthesis(
    synthesis: dict[str, Any],
    *,
    topic_atoms: dict[str, list[str]] | None = None,
    er_list: list[dict[str, Any]] | None = None,
    candidate_meta_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Audit every bucket of a synthesis dict.

    Returns a dict keyed by bucket name (``core`` / ``baseline`` /
    ``parallel`` / ``dataset`` / ``repo``), each containing a
    ``BucketAudit``.  Also returns a top-level
    ``critical_consistency_error_n`` sum used by
    ``compute_resource_status``.

    ``candidate_meta_index`` (optional) maps ``candidate_id`` →
    raw candidate dict with full ``url`` / ``abstract`` / ``year``
    fields.  When provided, ``_record`` carries those fields through
    to ``bucket.members`` so downstream CSVs / reports show the
    actual source URL and abstract snippet without a second join
    against the raw dump.
    """
    paper_groups = (synthesis.get("paper_groups") or {}) if isinstance(synthesis, dict) else {}
    candidate_pool = (synthesis.get("candidate_pool") or {}) if isinstance(synthesis, dict) else {}

    audits: dict[str, BucketAudit] = {
        "core": BucketAudit(),
        "baseline": BucketAudit(),
        "parallel": BucketAudit(),
        "dataset": BucketAudit(),
        "repo": BucketAudit(),
    }

    # ---- Core bucket (from synthesis.candidate_pool.core if present) ----
    for it in (candidate_pool.get("core") or []):
        cid = it.get("candidate_id") or it.get("id") or ""
        meta = (candidate_meta_index or {}).get(cid) if candidate_meta_index else None
        result = audit_candidate(it, role="core", topic_atoms=topic_atoms,
                                  meta=meta)
        _record(audits["core"], result, it, candidate_meta_index)

    # ---- Paper groups ----
    for entry, bucket, role in (
        (paper_groups.get("baseline") or [], audits["baseline"], "baseline"),
        (paper_groups.get("parallel") or [], audits["parallel"], "parallel"),
    ):
        for it in entry:
            if not isinstance(it, dict):
                continue
            cid = it.get("candidate_id") or it.get("id") or ""
            meta = (candidate_meta_index or {}).get(cid) if candidate_meta_index else None
            result = audit_candidate(it, role=role, topic_atoms=topic_atoms,
                                      meta=meta)
            _record(bucket, result, it, candidate_meta_index)

    # ---- ER core (reconcile with synthesis.core if it diverged) ----
    for r in (er_list or []):
        if not isinstance(r, dict):
            continue
        if (r.get("status") or "").lower() == "core":
            cid = r.get("candidate_id") or r.get("id") or ""
            meta = (candidate_meta_index or {}).get(cid) if candidate_meta_index else None
            result = audit_candidate(r, role="core", topic_atoms=topic_atoms,
                                      meta=meta)
            # Only record if this cid hasn't already been recorded in core
            existing_ids = {m["candidate_id"] for m in audits["core"].members}
            if result.candidate_id not in existing_ids:
                _record(audits["core"], result, r, candidate_meta_index)

    # ---- Datasets / repos ----
    for it in (candidate_pool.get("dataset") or []):
        cid = it.get("candidate_id") or it.get("id") or ""
        meta = (candidate_meta_index or {}).get(cid) if candidate_meta_index else None
        result = audit_candidate(it, role="dataset", topic_atoms=topic_atoms,
                                  meta=meta)
        _record(audits["dataset"], result, it, candidate_meta_index)
    for it in (candidate_pool.get("repo") or []):
        cid = it.get("candidate_id") or it.get("id") or ""
        meta = (candidate_meta_index or {}).get(cid) if candidate_meta_index else None
        result = audit_candidate(it, role="repo", topic_atoms=topic_atoms,
                                  meta=meta)
        _record(audits["repo"], result, it, candidate_meta_index)

    # ---- Critical error aggregate ----
    critical = sum(
        audits[b].critical_consistency_error_n for b in ("core", "baseline", "parallel")
    )
    return {
        "buckets": {b: audits[b].as_dict() for b in audits},
        "critical_consistency_error_n": critical,
        "metadata_mismatch_n": sum(
            audits[b].n_metadata_mismatch for b in audits
        ),
        "off_topic_core_n": audits["core"].n_off_topic,
    }


def _record(
    bucket: BucketAudit,
    result: ConsistencyResult,
    raw: dict[str, Any],
    meta_index: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Record a single audit result into the bucket counters.

    ``meta_index`` (optional) supplies richer candidate metadata
    (url / abstract / year / venue / authors) when the bucket-level
    candidate dict only carries ``candidate_id`` + ``title``.
    """
    bucket.n_total += 1
    enriched = dict(raw) if isinstance(raw, dict) else {}
    if meta_index:
        cid = result.candidate_id
        meta = meta_index.get(cid) or {}
        # Fill in any missing field from the rich meta dict.
        for k, v in meta.items():
            if v and not enriched.get(k):
                enriched[k] = v
    bucket.members.append({
        "candidate_id": result.candidate_id,
        "title": enriched.get("title") or enriched.get("name") or "",
        # Carried through so downstream CSVs / reports can show
        # the actual source URL, abstract snippet, and source type
        # without a second join against the raw dump.
        "url": enriched.get("url") or enriched.get("source_url") or "",
        "doi": enriched.get("doi") or "",
        "source_type": enriched.get("source_type") or enriched.get("source") or "",
        "year": enriched.get("year") or "",
        "venue": enriched.get("venue") or "",
        "authors": (
            ", ".join(enriched.get("authors") or [])
            if isinstance(enriched.get("authors"), list)
            else (enriched.get("authors") or "")
        ),
        "abstract_snippet":
            (enriched.get("abstract") or enriched.get("snippet") or "")[:300],
        "relation_to_topic": enriched.get("relation_to_topic") or "",
        "consistency_status": result.consistency_status,
        "axis_coverage": asdict(result.axis_coverage),
        "evidence_quality": asdict(result.evidence_quality),
        "decision_reason": result.decision_reason,
    })
    if result.consistency_status == "aligned":
        bucket.n_aligned += 1
    elif result.consistency_status == "proxy":
        bucket.n_proxy += 1
    elif result.consistency_status == "generic":
        bucket.n_generic += 1
    elif result.consistency_status == "metadata_mismatch":
        bucket.n_metadata_mismatch += 1
        bucket.critical_consistency_error_n += 1
    elif result.consistency_status == "off_topic":
        bucket.n_off_topic += 1
        bucket.critical_consistency_error_n += 1
    elif result.consistency_status == "insufficient_metadata":
        bucket.n_insufficient += 1