"""Evidence store: 内存版证据池 (SOP §5 + §13.1).

特点:
- in-memory dict, 跟 OneTopic MVP 一样不写 DB
- per project, 键 project_id
- dedup: paper 按 DOI / arxiv_id / 标题归一化去重 (SOP §7.3 Step 4)
- 自动入池: run_one_topic 跑完后, 把自动检索的 papers/datasets/baselines 同步进来
"""

from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from ..schemas import (
    BaselineHit,
    DatasetHit,
    EvidenceSummary,
    PaperHit,
)
from ..schemas_evidence import (
    EvidenceActionResponse,
    EvidenceItem,
    EvidenceLedgerResponse,
    DatasetManualCreate,
    PaperManualCreate,
    RepoManualCreate,
    ReviewUpdate,
)


# ---------- 内存存储 ---------- #


class _ProjectEvidence:
    """单个 project 的证据池."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.items: dict[str, EvidenceItem] = {}


_LEDGER: dict[str, _ProjectEvidence] = {}
_LEDGER_LOCK = threading.RLock()  # RLock 因为 _summary 在 update_review 锁内递归调用


def _get_project(project_id: str) -> _ProjectEvidence:
    """获取 / 懒创建 project 的证据池."""

    with _LEDGER_LOCK:
        if project_id not in _LEDGER:
            _LEDGER[project_id] = _ProjectEvidence(project_id)
        return _LEDGER[project_id]


def _summary(project_id: str) -> EvidenceLedgerResponse:
    proj = _get_project(project_id)
    papers = [e for e in proj.items.values() if e.evidence_type == "paper"]
    datasets = [e for e in proj.items.values() if e.evidence_type == "dataset"]
    repos = [e for e in proj.items.values() if e.evidence_type == "repo"]
    notes = [e for e in proj.items.values() if e.evidence_type in ("note", "custom")]
    accepted = sum(1 for e in proj.items.values() if e.review_status in ("accepted", "core"))
    core = sum(1 for e in proj.items.values() if e.review_status == "core")
    rejected = sum(1 for e in proj.items.values() if e.review_status == "rejected")
    needs = sum(1 for e in proj.items.values() if e.review_status == "needs_check")
    return EvidenceLedgerResponse(
        project_id=project_id,
        papers=papers, datasets=datasets, repos=repos, notes=notes,
        paper_count=len(papers), dataset_count=len(datasets), repo_count=len(repos),
        accepted_count=accepted, core_count=core, rejected_count=rejected, needs_check_count=needs,
    )


# ---------- dedup 工具 ---------- #


def _norm_title(t: str) -> str:
    """标题归一化: 小写 + 去标点 + 合并空白."""

    t = t.lower().strip()
    t = re.sub(r"[\s\W_]+", " ", t)
    return t.strip()


def _is_duplicate(new: EvidenceItem, existing: list[EvidenceItem]) -> EvidenceItem | None:
    """按 DOI / arxiv_id / 标题相似度 > 0.92 去重 (SOP §7.3 Step 4).

    DOI / arxiv_id 完全相同 → 必是重复.
    标题归一化后完全相同 → 重复.
    标题相似度 > 0.92 → 重复.
    """

    if new.evidence_type != "paper":
        return None
    if new.doi:
        for e in existing:
            if e.evidence_type == "paper" and e.doi and e.doi.lower() == new.doi.lower():
                return e
    if new.arxiv_id:
        for e in existing:
            if e.evidence_type == "paper" and e.arxiv_id and e.arxiv_id.lower() == new.arxiv_id.lower():
                return e
    new_t = _norm_title(new.title)
    if not new_t:
        return None
    for e in existing:
        if e.evidence_type != "paper":
            continue
        et = _norm_title(e.title)
        if not et:
            continue
        if et == new_t:
            return e
        # 简单字符集相似度: jaccard on word set
        s1 = set(new_t.split())
        s2 = set(et.split())
        if not s1 or not s2:
            continue
        jacc = len(s1 & s2) / len(s1 | s2)
        if jacc > 0.92:
            return e
    return None


# ---------- 自动入池 ---------- #


def ingest_auto_evidence(project_id: str, evidence: EvidenceSummary) -> None:
    """run_one_topic 跑完后, 把自动检索的 papers/datasets/baselines 入池.

    同一 project 多次调用 → dedup 跳过已存在的, 不覆盖.
    """

    proj = _get_project(project_id)
    existing = list(proj.items.values())

    for i, p in enumerate(evidence.papers):
        eid = f"auto_paper_{project_id[:6]}_{i+1:03d}"
        if eid in proj.items:
            continue
        item = EvidenceItem(
            evidence_id=eid, project_id=project_id,
            evidence_type="paper", source_mode="auto_search",
            title=p.title, url=p.url, year=p.year,
            authors=p.authors, abstract=p.summary,
            review_status="pending",
            tags=["auto"],
        )
        dup = _is_duplicate(item, existing)
        if dup:
            continue
        proj.items[eid] = item
        existing.append(item)

    for i, d in enumerate(evidence.datasets):
        eid = f"auto_dataset_{project_id[:6]}_{i+1:03d}"
        if eid in proj.items:
            continue
        item = EvidenceItem(
            evidence_id=eid, project_id=project_id,
            evidence_type="dataset", source_mode="auto_search",
            title=d.name or d.dataset_id, url=d.download,
            scale=d.scale, license=d.license,
            review_status="pending" if d.fit in ("低", "未知") else "accepted",
            tags=["auto", f"fit_{d.fit}", f"source_{d.source}"],
        )
        proj.items[eid] = item

    for i, b in enumerate(evidence.baselines):
        eid = f"auto_repo_{project_id[:6]}_{i+1:03d}"
        if eid in proj.items:
            continue
        item = EvidenceItem(
            evidence_id=eid, project_id=project_id,
            evidence_type="repo", source_mode="auto_search",
            title=b.name or b.baseline_id, url=b.repository_url,
            paper_title=b.paper_title,
            has_readme=True, has_training_script=True,
            review_status="pending",
            tags=["auto", f"diff_{b.reproduce_difficulty}", f"src_{b.source}"],
        )
        proj.items[eid] = item


# ---------- 手动添加 ---------- #


def add_paper_manual(project_id: str, body: PaperManualCreate) -> EvidenceActionResponse:
    proj = _get_project(project_id)
    eid = f"man_paper_{uuid.uuid4().hex[:8]}"
    item = EvidenceItem(
        evidence_id=eid, project_id=project_id,
        evidence_type="paper", source_mode="manual",
        title=body.title, url=body.url, year=body.year,
        authors=body.authors, doi=body.doi, arxiv_id=body.arxiv_id,
        abstract=body.abstract, user_note=body.user_note,
        tags=body.tags, review_status=body.review_status,
    )
    existing_papers = [e for e in proj.items.values() if e.evidence_type == "paper"]
    dup = _is_duplicate(item, existing_papers)
    if dup:
        return EvidenceActionResponse(
            ok=False, evidence_id=dup.evidence_id, evidence=dup,
            ledger_summary=_summary(project_id),
            message=f"重复论文 (DOI/arXiv/标题相似), 已存在 {dup.evidence_id}",
        )
    proj.items[eid] = item
    return EvidenceActionResponse(
        ok=True, evidence_id=eid, evidence=item,
        ledger_summary=_summary(project_id),
        message="论文已入池",
    )


def add_dataset_manual(project_id: str, body: DatasetManualCreate) -> EvidenceActionResponse:
    proj = _get_project(project_id)
    eid = f"man_dataset_{uuid.uuid4().hex[:8]}"
    item = EvidenceItem(
        evidence_id=eid, project_id=project_id,
        evidence_type="dataset", source_mode="manual",
        title=body.name, url=body.download,
        scale=body.scale, license=body.license,
        modality=body.modality, annotation=body.annotation,
        user_note=body.user_note, review_status=body.review_status,
    )
    proj.items[eid] = item
    return EvidenceActionResponse(
        ok=True, evidence_id=eid, evidence=item,
        ledger_summary=_summary(project_id),
        message="数据集已入池",
    )


def add_repo_manual(project_id: str, body: RepoManualCreate) -> EvidenceActionResponse:
    proj = _get_project(project_id)
    eid = f"man_repo_{uuid.uuid4().hex[:8]}"
    item = EvidenceItem(
        evidence_id=eid, project_id=project_id,
        evidence_type="repo", source_mode="manual",
        title=body.name, url=body.repository_url,
        paper_title=body.paper_title, license=body.license,
        has_readme=body.has_readme, has_env_file=body.has_env_file,
        has_training_script=body.has_training_script,
        has_eval_script=body.has_eval_script,
        user_note=body.user_note, review_status=body.review_status,
    )
    proj.items[eid] = item
    return EvidenceActionResponse(
        ok=True, evidence_id=eid, evidence=item,
        ledger_summary=_summary(project_id),
        message="仓库已入池",
    )


# ---------- 审核 / 删除 ---------- #


def update_review(evidence_id: str, body: ReviewUpdate) -> EvidenceActionResponse:
    with _LEDGER_LOCK:
        for proj in _LEDGER.values():
            if evidence_id in proj.items:
                old = proj.items[evidence_id]
                new_data = old.model_dump()
                new_data["review_status"] = body.review_status
                if body.user_note is not None:
                    new_data["user_note"] = body.user_note
                proj.items[evidence_id] = EvidenceItem(**new_data)
                return EvidenceActionResponse(
                    ok=True, evidence_id=evidence_id, evidence=proj.items[evidence_id],
                    ledger_summary=_summary(proj.project_id),
                    message=f"状态已更新: {body.review_status}",
                )
    return EvidenceActionResponse(
        ok=False, evidence_id=evidence_id, evidence=None,
        ledger_summary=EvidenceLedgerResponse(project_id=""),
        message=f"evidence_id {evidence_id} 不存在",
    )


def delete_evidence(evidence_id: str) -> EvidenceActionResponse:
    with _LEDGER_LOCK:
        for proj in _LEDGER.values():
            if evidence_id in proj.items:
                del proj.items[evidence_id]
                return EvidenceActionResponse(
                    ok=True, evidence_id=evidence_id, evidence=None,
                    ledger_summary=_summary(proj.project_id),
                    message="已删除",
                )
    return EvidenceActionResponse(
        ok=False, evidence_id=evidence_id, evidence=None,
        ledger_summary=EvidenceLedgerResponse(project_id=""),
        message=f"evidence_id {evidence_id} 不存在",
    )


# ---------- 查询 ---------- #


def get_ledger(project_id: str) -> EvidenceLedgerResponse:
    return _summary(project_id)


def get_item(evidence_id: str) -> EvidenceItem | None:
    with _LEDGER_LOCK:
        for proj in _LEDGER.values():
            if evidence_id in proj.items:
                return proj.items[evidence_id]
    return None


# ---------- 测试用重置 ---------- #


def reset_all() -> None:
    """测试用: 清空全部 evidence store. 生产不要用."""

    with _LEDGER_LOCK:
        _LEDGER.clear()
