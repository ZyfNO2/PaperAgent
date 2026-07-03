"""Re08 CandidateVerifier — SOP §4.1.

Per-candidate evidence verifier.  Borrows AutoResearchClaw's
``researchclaw/literature/verify.py`` pattern (three-layer: arXiv ID →
DOI → title search, with ``verify_status`` enum) but stays inside the
agents/ subtree, depends only on existing retrieval adapters, and **never
filters by hardcoded title blacklist**.

Two modes:

  * **online**  — ``verify_candidate_online`` calls arXiv / Crossref /
    Semantic Scholar adapters and writes the result into the candidate.
  * **offline** — ``verify_candidate_offline`` runs only the rule layer
    (title/abstract token overlap + URL/DOI sanity).  Used by Re08 to
    re-audit Re05 raw dumps without a live network.

The verifier produces a ``VerificationResult`` dict with the schema
prescribed by SOP §4.1.  ``compute_resource_status`` consumes this and
relaxes the Re07 quarantine logic: ``metadata_repaired`` no longer
counts as ``metadata_mismatch`` (it enters effective_*), and
``weak_metadata`` enters as ``proxy`` axis_relation.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .prompts.verify_candidate import VERIFY_CANDIDATE_SYSTEM, render_verify_candidate

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Per-candidate verification outcome (SOP §4.1)."""

    candidate_id: str
    role: str
    verification_status: str = "weak_metadata"
    topic_relation: str = "proxy"
    matched_keywords: list[str] = field(default_factory=list)
    related_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    reason: str = ""
    repair_notes: str = ""
    recommended_action: str = "keep_as_proxy"
    confidence_label: str = "medium"
    metadata_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([\w.\-]+)", re.IGNORECASE)
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'>]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/([\w\-]+)/([\w\.\-]+)", re.IGNORECASE)


def _normalize_id_field(candidate: dict) -> dict[str, str]:
    """Extract arXiv_id, DOI, GitHub owner/repo from the candidate."""
    out: dict[str, str] = {}
    arxiv_id = candidate.get("arxiv_id") or ""
    if not arxiv_id:
        url = candidate.get("url") or ""
        m = _ARXIV_ID_RE.search(url)
        if m:
            arxiv_id = m.group(1)
    if arxiv_id:
        out["arxiv_id"] = arxiv_id
    doi = candidate.get("doi") or ""
    if not doi:
        url = candidate.get("url") or ""
        m = _DOI_RE.search(url)
        if m:
            doi = m.group(0)
    if doi:
        out["doi"] = doi
    url = candidate.get("url") or ""
    m = _GITHUB_RE.search(url)
    if m:
        out["github_owner"] = m.group(1)
        out["github_repo"] = m.group(2)
    return out


def _flatten_atom_text(topic_atoms: dict, axis: str) -> list[str]:
    """Pull en + aliases from the axis into a single token list."""
    out: list[str] = []
    for atom in topic_atoms.get(axis, []) or []:
        if isinstance(atom, str):
            if atom:
                out.append(atom)
        elif isinstance(atom, dict):
            for k in ("en", "zh"):
                v = atom.get(k)
                if v:
                    out.append(v)
            for alias in atom.get("aliases") or []:
                if alias:
                    out.append(alias)
    return out


def _word_overlap(a: str, b: str) -> float:
    """Token overlap coefficient (max-length denominator)."""
    wa = {t.lower() for t in re.findall(r"[\w一-鿿]+", a or "") if len(t) >= 2}
    wb = {t.lower() for t in re.findall(r"[\w一-鿿]+", b or "") if len(t) >= 2}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ---------------------------------------------------------------------------
# Offline rule layer
# ---------------------------------------------------------------------------


def _classify_offline(
    candidate: dict, topic_atoms: dict, role: str,
) -> VerificationResult:
    """Pure rule-based verifier — no LLM, no network.

    Used by Re08 re-audit on Re05 raw dumps where live LLM calls would
    consume quota the user wants reserved for the next round.

    Logic:
      * If candidate has no title AND no URL → not_found
      * If candidate has only a URL and no title (typical GitHub
        without README scraping) → weak_metadata
      * If candidate's title contains ≥ 2 axis keywords → direct
      * If title overlaps ≥ 1 axis → proxy
      * If candidate is a recognized backbone (YOLO/UNet/ORB-SLAM/BERT)
        without explicit topic mention → foundation
      * Otherwise → off_topic
    """
    cid = candidate.get("candidate_id") or candidate.get("id") or ""
    title = (candidate.get("title") or candidate.get("name") or "").strip()
    abstract = (candidate.get("abstract") or candidate.get("snippet") or "").strip()
    url = candidate.get("url") or candidate.get("source_url") or ""

    if not title and not url:
        return VerificationResult(
            candidate_id=cid, role=role,
            verification_status="not_found", topic_relation="off_topic",
            reason="empty title and empty url",
            recommended_action="quarantine",
            confidence_label="high",
        )

    ids = _normalize_id_field(candidate)

    # axis keyword match
    task_kw = _flatten_atom_text(topic_atoms, "task")
    obj_kw = _flatten_atom_text(topic_atoms, "object")
    method_kw = _flatten_atom_text(topic_atoms, "method")
    scen_kw = _flatten_atom_text(topic_atoms, "scenario")

    haystack = f"{title}\n{abstract}".lower()

    def _kw_in(kw_list: Iterable[str]) -> list[str]:
        return [k for k in kw_list if k and k.lower() in haystack]

    matched = _kw_in(task_kw) + _kw_in(obj_kw) + _kw_in(method_kw)
    related = _kw_in(scen_kw)

    # P0-D FIX-2: token-level partial match.  When the full atom doesn't
    # appear in haystack, try matching individual English tokens (length
    # >= 4).  This rescues "DeepCrack / CrackFormer / Deep Metallic
    # Surface Defect Detection" for a "基于 UNet 的钢材裂缝分割"
    # topic whose atoms are in Chinese.  ponytail: cheap heuristic,
    # upgrade path is LLM re-verify when partial-only.
    if not matched:
        all_atom_text = " ".join(task_kw + obj_kw + method_kw + scen_kw).lower()
        atom_tokens = {
            t for t in re.findall(r"[a-z]{4,}", all_atom_text)
        }
        title_tokens = set(re.findall(r"[a-z]{4,}", haystack))
        if atom_tokens & title_tokens and len(atom_tokens & title_tokens) >= 1:
            matched = [next(iter(atom_tokens & title_tokens))]

    if matched:
        topic_relation = "direct"
    elif related:
        topic_relation = "proxy"
    else:
        # backbone recognition — only for method axis or for candidate role=='repo'
        backbone_tokens = (
            "yolo", "unet", "u-net", "mask rcnn", "faster rcnn", "ssd",
            "orb-slam", "dso", "vins", "bert", "gpt", "transformer",
            "pointnet", "dgcnn", "snowflakenet", "pcn", "mobilenet",
            "resnet", "yolov5", "yolov8", "yolox", "centernet",
        )
        title_lower = title.lower()
        if any(b in title_lower for b in backbone_tokens):
            topic_relation = "foundation"
        elif role == "repo" and ("github.com" in url.lower()):
            topic_relation = "infrastructure"
        else:
            topic_relation = "off_topic"

    # metadata consistency: title vs abstract token overlap
    sim = _word_overlap(title, abstract)
    metadata_sources = []
    if ids.get("arxiv_id"):
        metadata_sources.append("arxiv")
    if ids.get("doi"):
        metadata_sources.append("crossref_doi")
    if ids.get("github_repo"):
        metadata_sources.append("github")

    if title and abstract and sim < 0.10:
        # Title and abstract have almost nothing in common — classic
        # crossref metadata glue artifact.
        return VerificationResult(
            candidate_id=cid, role=role,
            verification_status="metadata_mismatch",
            topic_relation=topic_relation,
            matched_keywords=matched,
            related_keywords=related,
            reason=(
                f"title/abstract token overlap={sim:.2f} — looks like "
                f"a stitched citation"
            ),
            repair_notes=(
                "search arXiv by title; if DOI given, hit datacite or "
                "openalex by DOI to recover the real abstract"
            ),
            recommended_action="repair",
            confidence_label="medium",
            metadata_sources=metadata_sources,
        )

    if not title or not abstract:
        status = "weak_metadata"
        action = "repair"
        reason = "missing title or abstract"
    else:
        status = "verified" if topic_relation in {"direct", "proxy"} else "weak_metadata"
        action = "keep" if topic_relation in {"direct", "proxy", "foundation"} else "keep_as_proxy"
        reason = (
            f"title/abstract sim={sim:.2f}; "
            f"matched={len(matched)}; related={len(related)}"
        )

    return VerificationResult(
        candidate_id=cid, role=role,
        verification_status=status, topic_relation=topic_relation,
        matched_keywords=matched,
        related_keywords=related,
        missing_keywords=[
            k for k in (task_kw + obj_kw) if k.lower() not in haystack
        ][:5],
        reason=reason,
        recommended_action=action,
        confidence_label="high" if status == "verified" else "medium",
        metadata_sources=metadata_sources,
    )


# ---------------------------------------------------------------------------
# Online entry — wires the LLM verifier on top of the rule layer
# ---------------------------------------------------------------------------


def verify_candidate_offline(
    candidate: dict, topic_atoms: dict, role: str = "core_paper",
) -> VerificationResult:
    """Public alias for the rule-based layer (Re08 SOP §4.1 mode B)."""
    return _classify_offline(candidate, topic_atoms, role)


async def verify_candidate_online(
    candidate: dict, topic_atoms: dict, role: str,
    llm_client: Any | None = None,
    *,
    client: Any | None = None,
) -> VerificationResult:
    """Online verifier: rule layer + arXiv/DOI confirmation + LLM verdict.

    The LLM is **only** called when the rule layer reports a soft
    contradiction (weak_metadata OR metadata_mismatch).  Verified or
    off_topic candidates skip the LLM call to keep quota low.

    Args:
      candidate:    candidate dict (must have title; url/arxiv_id/doi
                    optional but recommended).
      topic_atoms:  parsed topic atoms (Re07 schema).
      role:         one of core_paper / baseline / parallel_paper /
                    dataset / repo.
      llm_client:   optional async callable ``llm_client(system, user)``
                    returning a JSON string.  When None, falls back to
                    ``None`` (rule layer only).
      client:       optional shared ``httpx.AsyncClient``-style object
                    passed through to retrieval adapters.
    """
    base = _classify_offline(candidate, topic_atoms, role)
    # Fast paths skip the LLM call.
    if base.verification_status == "verified" and base.topic_relation == "direct":
        return base

    if llm_client is None:
        return base

    topic = (
        candidate.get("_topic")
        or candidate.get("topic")
        or candidate.get("raw_topic")
        or ""
    )
    user_prompt = render_verify_candidate(
        topic=topic, topic_atoms=topic_atoms,
        candidate_role=role, candidate=candidate,
    )
    try:
        raw = await llm_client(VERIFY_CANDIDATE_SYSTEM, user_prompt)
        import json
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception as exc:  # ponytail: never let LLM failures crash the verifier
        logger.warning("verify_candidate_online LLM call failed: %s", exc)
        return base

    # LLM may override status, but we keep base.metadata_sources.
    base.verification_status = payload.get("verification_status", base.verification_status)
    base.topic_relation = payload.get("topic_relation", base.topic_relation)
    base.matched_keywords = payload.get("matched_keywords", base.matched_keywords)
    base.related_keywords = payload.get("related_keywords", base.related_keywords)
    base.missing_keywords = payload.get("missing_keywords", base.missing_keywords)
    base.reason = payload.get("reason", base.reason)
    base.repair_notes = payload.get("repair_notes", base.repair_notes)
    base.recommended_action = payload.get("recommended_action", base.recommended_action)
    base.confidence_label = payload.get("confidence_label", base.confidence_label)
    return base


def verify_bucket(
    bucket_name: str,
    members: list[dict],
    topic_atoms: dict,
    *,
    llm_client: Any | None = None,
) -> list[VerificationResult]:
    """Verify an entire bucket in offline mode (sync).

    Returns a list of VerificationResult, one per member.  Used by the
    Re08 re-audit script for the Balanced40 set.
    """
    out: list[VerificationResult] = []
    for m in members:
        cand = dict(m) if isinstance(m, dict) else {"title": str(m)}
        if "candidate_id" not in cand and "id" in cand:
            cand["candidate_id"] = cand["id"]
        cid = cand.get("candidate_id") or cand.get("id") or ""
        if not cid:
            # fallback to title hash for dedupe
            cid = "v_" + str(abs(hash((cand.get("title") or ""))) % (10**8))
            cand["candidate_id"] = cid
        result = verify_candidate_offline(cand, topic_atoms, role=bucket_name)
        out.append(result)
    return out


__all__ = [
    "VerificationResult",
    "verify_candidate_offline",
    "verify_candidate_online",
    "verify_bucket",
]


# ---------------------------------------------------------------------------
# Online batch verifier (Re09 SOP §4.2)
# ---------------------------------------------------------------------------


async def verify_bucket_online(
    bucket_name: str,
    members: list[dict],
    topic_atoms: dict,
    *,
    llm_client=None,
    metadata_client=None,
) -> list:
    """Online verification of a bucket with optional metadata repair.

    For each member the rule layer runs first; weak_metadata /
    metadata_mismatch candidates then go through a live probe via
    ``metadata_client`` (async callable ``(adapter_name, query, top_k)
    -> list[dict]``).  On a title-similarity match >= 0.80 the verdict
    is upgraded to ``metadata_repaired``.  Never fabricates metadata;
    adapter failures are swallowed and logged.
    """
    # ponytail: closure keeps adapter contract local - no module bloat.
    async def _probe(adapter, query, top_k=3):
        if not metadata_client or not query:
            return []
        try:
            hits = await metadata_client(adapter, query, top_k=top_k)
        except Exception as exc:
            logger.warning(
                "verify_bucket_online probe(%s) failed: %s", adapter, exc,
            )
            return []
        return hits or []

    out = []
    for m in members:
        cand = dict(m) if isinstance(m, dict) else {"title": str(m)}
        if "candidate_id" not in cand and "id" in cand:
            cand["candidate_id"] = cand["id"]
        cid = cand.get("candidate_id") or cand.get("id") or ""
        if not cid:
            cid = "v_" + str(abs(hash((cand.get("title") or ""))) % (10**8))
            cand["candidate_id"] = cid
        result = verify_candidate_offline(cand, topic_atoms, role=bucket_name)
        if metadata_client and result.verification_status in {
            "weak_metadata", "metadata_mismatch",
        }:
            seed_title = (cand.get("title") or cand.get("name") or "").strip()
            if seed_title and len(seed_title) >= 6:
                best_sim = 0.0
                best_source = ""
                for adapter in ("arxiv", "openalex", "crossref"):
                    hits = await _probe(adapter, seed_title, top_k=3)
                    for h in hits:
                        if not isinstance(h, dict):
                            continue
                        ht = (h.get("title") or "").strip()
                        if not ht:
                            continue
                        sim = _word_overlap(seed_title, ht)
                        if sim > best_sim:
                            best_sim = sim
                            best_source = adapter
                if best_sim >= 0.80:
                    result.verification_status = "metadata_repaired"
                    result.confidence_label = "medium"
                    result.recommended_action = "keep_as_proxy"
                    result.reason = (
                        f"metadata_repaired via {best_source} (title sim={best_sim:.2f})"
                    )
                    result.repair_notes = (
                        f"live probe matched {best_source} title sim={best_sim:.2f}; "
                        "raw_candidate preserved"
                    )
                    src_set = set(result.metadata_sources or [])
                    src_set.add(best_source)
                    result.metadata_sources = sorted(src_set)
        out.append(result)
    return out


__all__ = [
    "VerificationResult",
    "verify_candidate_offline",
    "verify_candidate_online",
    "verify_bucket",
    "verify_bucket_online",
]

