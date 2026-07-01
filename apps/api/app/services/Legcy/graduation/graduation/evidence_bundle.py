"""Session 62 M3: EvidenceBundleBuilder — bind real evidence to each direction.

ponytail: 不编造, 不编 paper/dataset; 复用现有 ev_store + retrieval_service + local_rag.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from .. import evidence as ev_store
from ..paper_library import local_rag, storage as pl_storage
from ..retrieval import orchestrator as retrieval_service
from ...schemas_graduation_direction import EvidenceBundle, EvidenceBundleRef

logger = logging.getLogger(__name__)


_MAX_PER_TYPE = 5
_MAX_RAG_REFS = 5


def _retrieval_paper_refs(project_id: str, top_k: int = _MAX_PER_TYPE) -> list[EvidenceBundleRef]:
    """从 S61 最近一次 retrieval run 抽 paper 候选."""
    run = retrieval_service.get_last_run(project_id)
    if run is None or not run.candidates:
        return []
    refs: list[EvidenceBundleRef] = []
    for c in run.candidates:
        if c.candidate_type != "paper":
            continue
        refs.append(EvidenceBundleRef(
            ref_type="paper",
            ref_id=c.candidate_id,
            title=c.title,
            url=c.url,
        ))
        if len(refs) >= top_k:
            break
    return refs


def _retrieval_dataset_refs(project_id: str, top_k: int = _MAX_PER_TYPE) -> list[EvidenceBundleRef]:
    run = retrieval_service.get_last_run(project_id)
    if run is None or not run.candidates:
        return []
    refs: list[EvidenceBundleRef] = []
    for c in run.candidates:
        if c.candidate_type != "dataset":
            continue
        refs.append(EvidenceBundleRef(
            ref_type="dataset",
            ref_id=c.candidate_id,
            title=c.title,
            url=c.url,
        ))
        if len(refs) >= top_k:
            break
    return refs


def _retrieval_repo_refs(project_id: str, top_k: int = _MAX_PER_TYPE) -> list[EvidenceBundleRef]:
    run = retrieval_service.get_last_run(project_id)
    if run is None or not run.candidates:
        return []
    refs: list[EvidenceBundleRef] = []
    for c in run.candidates:
        if c.candidate_type != "repo":
            continue
        refs.append(EvidenceBundleRef(
            ref_type="repo",
            ref_id=c.candidate_id,
            title=c.title,
            url=c.url,
        ))
        if len(refs) >= top_k:
            break
    return refs


def _ledger_paper_refs(project_id: str, top_k: int = _MAX_PER_TYPE) -> list[EvidenceBundleRef]:
    """补充从 Evidence Ledger 取 paper 证据 (若 retrieval 没有)."""
    ledger = ev_store.get_ledger(project_id)
    refs: list[EvidenceBundleRef] = []
    for p in ledger.papers:
        refs.append(EvidenceBundleRef(
            ref_type="paper",
            ref_id=p.evidence_id,
            title=p.title,
            url=p.url or p.download,
        ))
        if len(refs) >= top_k:
            break
    return refs


def _local_rag_refs(project_id: str, query: str, top_k: int = _MAX_RAG_REFS) -> list[EvidenceBundleRef]:
    """调 S60 本地 RAG (纯本地检索, 不依赖 LLM)."""
    if not query:
        return []
    try:
        outcome = local_rag.ask_local_rag(project_id=project_id, question=query, top_k=top_k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("local_rag.ask_local_rag failed: %s", exc)
        return []
    if outcome.no_hit:
        return []
    refs: list[EvidenceBundleRef] = []
    for r in outcome.evidence_refs:
        # 尝试从 storage 拿 paper title
        title = ""
        try:
            rec = pl_storage.load_record(project_id, r.paper_id)
            title = rec.title if rec else r.paper_id
        except Exception:  # noqa: BLE001
            title = r.paper_id
        refs.append(EvidenceBundleRef(
            ref_type="rag_chunk",
            ref_id=r.chunk_id,
            title=title,
            quote=r.quote,
        ))
    return refs


def _merge_unique(*sources: Iterable[EvidenceBundleRef]) -> list[EvidenceBundleRef]:
    seen: set[str] = set()
    out: list[EvidenceBundleRef] = []
    for src in sources:
        for r in src:
            key = f"{r.ref_type}:{r.ref_id}"
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
    return out


def _gap_lines(
    *,
    has_paper: bool,
    has_dataset: bool,
    has_repo: bool,
    has_local_rag: bool,
) -> list[str]:
    gaps: list[str] = []
    if not has_paper:
        gaps.append("论文候选为空, 建议补一轮综述检索")
    if not has_dataset:
        gaps.append("公开数据集为空, 需要降级方向或自采")
    if not has_repo:
        gaps.append("可复现工程为空, 需自己搭 baseline")
    if not has_local_rag:
        gaps.append("本地文献库无相关片段, 可上传或补抓 PDF")
    return gaps


@dataclass
class _Counts:
    paper: int = 0
    dataset: int = 0
    repo: int = 0
    rag_ref: int = 0
    gaps: int = 0


def build_evidence_bundle(
    project_id: str,
    *,
    use_last_retrieval: bool = True,
    use_local_rag: bool = True,
    local_rag_query: str = "",
) -> tuple[EvidenceBundle, dict[str, int]]:
    """聚合 S61 + S60 + ledger 证据.

    返回 (bundle, source_counts). source_counts 用于开发者窗口.
    """

    counts = _Counts()

    papers: list[EvidenceBundleRef] = []
    datasets: list[EvidenceBundleRef] = []
    repos: list[EvidenceBundleRef] = []

    if use_last_retrieval:
        papers.extend(_retrieval_paper_refs(project_id))
        datasets.extend(_retrieval_dataset_refs(project_id))
        repos.extend(_retrieval_repo_refs(project_id))

    # ledger 补齐 (S61 没跑过)
    ledger = ev_store.get_ledger(project_id)
    if not papers and ledger.papers:
        papers.extend(_ledger_paper_refs(project_id))
    if not datasets and ledger.datasets:
        for d in ledger.datasets[:_MAX_PER_TYPE]:
            datasets.append(EvidenceBundleRef(
                ref_type="dataset",
                ref_id=d.evidence_id,
                title=d.title,
                url=d.url or d.download,
            ))
    if not repos and ledger.repos:
        for r in ledger.repos[:_MAX_PER_TYPE]:
            repos.append(EvidenceBundleRef(
                ref_type="repo",
                ref_id=r.evidence_id,
                title=r.title,
                url=r.url or r.download,
            ))

    counts.paper = len(papers)
    counts.dataset = len(datasets)
    counts.repo = len(repos)

    rag_refs: list[EvidenceBundleRef] = []
    if use_local_rag:
        rag_refs = _local_rag_refs(project_id, local_rag_query or "")
    counts.rag_ref = len(rag_refs)

    gaps = _gap_lines(
        has_paper=counts.paper > 0,
        has_dataset=counts.dataset > 0,
        has_repo=counts.repo > 0,
        has_local_rag=counts.rag_ref > 0,
    )
    counts.gaps = len(gaps)

    bundle = EvidenceBundle(
        papers=_merge_unique(papers),
        datasets=_merge_unique(datasets),
        repos=_merge_unique(repos),
        rag_refs=_merge_unique(rag_refs),
        gaps=gaps,
    )
    return bundle, {
        "paper": counts.paper,
        "dataset": counts.dataset,
        "repo": counts.repo,
        "rag_ref": counts.rag_ref,
        "gaps": counts.gaps,
    }


if __name__ == "__main__":
    # ponytail: self-check
    bundle, counts = build_evidence_bundle(
        "ot_no_such_project", use_last_retrieval=True, use_local_rag=True, local_rag_query="裂缝",
    )
    assert counts["paper"] == 0, counts
    assert counts["dataset"] == 0, counts
    assert "论文候选为空" in bundle.gaps[0], bundle.gaps
    print(f"OK evidence_bundle self-check (counts={counts}, gaps={len(bundle.gaps)})")