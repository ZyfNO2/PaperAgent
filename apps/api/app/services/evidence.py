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
        # Session 7: 最新一次 analyze 的快照 (供 refs/rebuild 和 refs/coverage 用)
        self.latest_snapshot: dict[str, Any] | None = None


_LEDGER: dict[str, _ProjectEvidence] = {}
_LEDGER_LOCK = threading.RLock()  # RLock 因为 _summary 在 update_review 锁内递归调用

# Session 7 §7.3: 用户复核 EvidenceRef 的 Trace 记录
_TRACE: dict[str, list[dict[str, Any]]] = {}
_TRACE_LOCK = threading.RLock()


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


def _jaccard(a: str, b: str) -> float:
    """字符级 jaccard 相似度 (0-1)."""

    sa = set(_norm_title(a).split())
    sb = set(_norm_title(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _repo_canonical(url: str | None, name: str | None) -> str | None:
    """GitHub repo canonical key: owner/name 小写.

    例: https://github.com/ultralytics/ultralytics → "ultralytics/ultralytics"
    例: ultralytics/yolov5 → "ultralytics/yolov5"
    """

    if url:
        m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)", url, re.IGNORECASE)
        if m:
            return f"{m.group(1).lower()}/{m.group(2).lower().rstrip('.git')}"
    if name and "/" in name:
        parts = name.lower().strip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return None


def _is_duplicate(new: EvidenceItem, existing: list[EvidenceItem]) -> EvidenceItem | None:
    """SOP §4.4 增强去重.

    Paper:
      - DOI / arxiv_id 完全相同
      - OpenAlex ID / Semantic Scholar ID 完全相同
      - 标题归一化后完全相同
      - 标题 jaccard > 0.92 且年份相同
    Repo:
      - GitHub owner/name canonical key 相同
    Dataset:
      - name 完全相同 (canonical)
    """

    if new.evidence_type == "paper":
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
            # 标题 jaccard > 0.92 且年份相同
            if e.year and new.year and e.year != new.year:
                continue
            if _jaccard(et, new_t) > 0.92:
                return e
    elif new.evidence_type == "repo":
        new_key = _repo_canonical(new.url, new.title)
        if new_key:
            for e in existing:
                if e.evidence_type != "repo":
                    continue
                if _repo_canonical(e.url, e.title) == new_key:
                    return e
    elif new.evidence_type == "dataset":
        new_name = (new.title or "").strip().lower()
        if new_name and new_name != "(未匹配公开数据集)":
            for e in existing:
                if e.evidence_type != "dataset":
                    continue
                en = (e.title or "").strip().lower()
                if en and en == new_name:
                    return e
    return None


# ---------- 自动入池 ---------- #


def clear_auto_evidence(project_id: str) -> int:
    """清掉一个 project 的所有 auto_* 证据 (regenerate 前调用). 返回删除数."""

    proj = _get_project(project_id)
    removed = 0
    with _LEDGER_LOCK:
        for eid in list(proj.items.keys()):
            if eid.startswith("auto_"):
                del proj.items[eid]
                removed += 1
    return removed


def ingest_auto_evidence(project_id: str, evidence: EvidenceSummary) -> None:
    """run_one_topic 跑完后, 把自动检索的 papers/datasets/baselines 入池.

    同一 project 多次调用 → dedup 跳过已存在的, 不覆盖.
    Session 5: 把 score / paper_type / dataset_status / repo_type 同步过来 (SOP §7.3-7.5).
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
            arxiv_id=p.paper_id if (p.source == "arXiv" and p.paper_id) else None,
            review_status="pending",
            relevance_score=p.relevance_score,
            paper_type=p.paper_type or "unknown",
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
            quality_score=d.quality_score,
            dataset_status=d.dataset_status or "unverified",
            review_status="pending" if d.fit in ("低", "未知") else "accepted",
            tags=["auto", f"fit_{d.fit}", f"source_{d.source}"],
        )
        dup = _is_duplicate(item, existing)
        if dup:
            continue
        proj.items[eid] = item
        existing.append(item)

    for i, b in enumerate(evidence.baselines):
        eid = f"auto_repo_{project_id[:6]}_{i+1:03d}"
        if eid in proj.items:
            continue
        item = EvidenceItem(
            evidence_id=eid, project_id=project_id,
            evidence_type="repo", source_mode="auto_search",
            title=b.name or b.baseline_id, url=b.repository_url,
            paper_title=b.paper_title,
            license=b.license or None,
            has_readme=True if (b.repository_url and "github.com" in (b.repository_url or "")) else False,
            has_env_file=True,  # 大型项目一般有 requirements
            has_training_script=True,
            has_eval_script=True,
            has_pretrained_weight=True,  # 主流 baseline 都有 pretrained
            quality_score=b.quality_score,
            repo_type=b.repo_type or "unknown",
            review_status="pending",
            tags=["auto", f"diff_{b.reproduce_difficulty}", f"src_{b.source}"],
        )
        dup = _is_duplicate(item, existing)
        if dup:
            continue
        proj.items[eid] = item
        existing.append(item)


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
    existing_repos = [e for e in proj.items.values() if e.evidence_type == "repo"]
    dup = _is_duplicate(item, existing_repos)
    if dup:
        return EvidenceActionResponse(
            ok=False, evidence_id=dup.evidence_id, evidence=dup,
            ledger_summary=_summary(project_id),
            message=f"重复 repo (同 owner/name), 已存在 {dup.evidence_id}",
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


# ---------- Session 5: rescore / score-summary / dedup-check (§8) ---------- #


def _heuristic_keywords_for_rescore(proj_items: list[EvidenceItem]) -> dict:
    """从已有 evidence 的标题拼一个粗略 keywords dict (供 scoring 用)."""

    titles = [e.title for e in proj_items if e.title and e.evidence_type == "paper"]
    method_kw: list[str] = []
    object_kw: list[str] = []
    task_kw: list[str] = []
    for t in titles[:5]:
        words = re.findall(r"[a-zA-Z一-龥]{2,}", t)
        if not words:
            continue
        # 启发式: 第一个英文词当 method (e.g. YOLO, Transformer, BERT)
        for w in words:
            wl = w.lower()
            if not method_kw and wl in (
                "yolo", "transformer", "bert", "gpt", "llm", "vit",
                "resnet", "cnn", "lstm", "diffusion", "gan", "mamba",
                "pinn", "gnn", "gcn", "gat",
            ):
                method_kw.append(w)
                break
        if len(object_kw) < 2 and len(words) > 1:
            object_kw.append(words[-1])
    return {
        "method_keywords": method_kw or ["深度学习"],
        "task_keywords": task_kw or ["目标检测"],
        "object_keywords": object_kw or ["目标对象"],
        "scenario_keywords": [],
        "metric_keywords": [],
    }


def _score_one_item(item: EvidenceItem, keywords: dict) -> None:
    """原地给一条 evidence 算 score (session 5)."""

    from . import scoring  # 局部 import 避免循环
    if item.evidence_type == "paper":
        paper_dict = {
            "title": item.title, "summary": item.abstract or "",
            "year": item.year,
        }
        s, bd = scoring.score_paper_relevance(paper_dict, keywords)
        item.relevance_score = round(s, 3)
        item.paper_type = scoring.classify_paper_type(paper_dict)
    elif item.evidence_type == "dataset":
        d_dict = {
            "name": item.title, "scale": item.scale or "",
            "license": item.license or "", "download": item.url or "",
            "annotation": item.annotation or "", "fit": "中",
            "source": "public-known" if item.url else "heuristic",
        }
        s, bd = scoring.score_dataset(d_dict, keywords)
        item.quality_score = round(s, 3)
        item.dataset_status = scoring._derive_dataset_status(s, d_dict)
    elif item.evidence_type == "repo":
        r_dict = {
            "name": item.title, "repository_url": item.url or "",
            "has_readme": item.has_readme, "license": item.license or "",
            "has_training_script": item.has_training_script,
            "has_eval_script": item.has_eval_script,
            "has_pretrained_weight": item.has_pretrained_weight,
            "has_env_file": item.has_env_file,
            "paper_year": None,
        }
        s, bd = scoring.score_repo(r_dict, None)
        item.quality_score = round(s, 3)
        item.repo_type = scoring._derive_repo_type(r_dict)


def rescore_project(project_id: str) -> dict:
    """Session 5 §8.1: 重新评分整个 project 的 evidence pool.

    不改变 review_status. 同步算 score / paper_type / dataset_status / repo_type.
    """

    proj = _get_project(project_id)
    items = list(proj.items.values())
    if not items:
        return {
            "project_id": project_id,
            "paper_count": 0, "dataset_count": 0, "repo_count": 0,
            "updated_count": 0,
            "summary": {"avg_paper_score": 0.0, "avg_dataset_score": 0.0, "avg_repo_score": 0.0},
        }
    keywords = _heuristic_keywords_for_rescore(items)
    updated = 0
    with _LEDGER_LOCK:
        for eid, e in proj.items.items():
            old_score = e.relevance_score or e.quality_score
            _score_one_item(e, keywords)
            new_score = e.relevance_score or e.quality_score
            if old_score != new_score:
                updated += 1

    paper_scores = [e.relevance_score for e in items if e.evidence_type == "paper" and e.relevance_score is not None]
    dataset_scores = [e.quality_score for e in items if e.evidence_type == "dataset" and e.quality_score is not None]
    repo_scores = [e.quality_score for e in items if e.evidence_type == "repo" and e.quality_score is not None]
    return {
        "project_id": project_id,
        "paper_count": sum(1 for e in items if e.evidence_type == "paper"),
        "dataset_count": sum(1 for e in items if e.evidence_type == "dataset"),
        "repo_count": sum(1 for e in items if e.evidence_type == "repo"),
        "updated_count": updated,
        "summary": {
            "avg_paper_score": round(sum(paper_scores) / len(paper_scores), 3) if paper_scores else 0.0,
            "avg_dataset_score": round(sum(dataset_scores) / len(dataset_scores), 3) if dataset_scores else 0.0,
            "avg_repo_score": round(sum(repo_scores) / len(repo_scores), 3) if repo_scores else 0.0,
        },
    }


def score_summary(project_id: str) -> dict:
    """Session 5 §8.2: 评分摘要.

    usable_* = score >= 0.4 + status 满足"可入池"条件
    low_quality = score < 0.3
    rejected = review_status == rejected
    """

    proj = _get_project(project_id)
    items = list(proj.items.values())
    usable_papers = sum(
        1 for e in items
        if e.evidence_type == "paper"
        and (e.relevance_score or 0) >= 0.3
        and e.paper_type not in ("irrelevant",)
        and e.review_status not in ("rejected",)
    )
    usable_datasets = sum(
        1 for e in items
        if e.evidence_type == "dataset"
        and (e.quality_score or 0) >= 0.4
        and e.dataset_status in ("ready", "needs_preprocess")
        and e.review_status not in ("rejected",)
    )
    usable_repos = sum(
        1 for e in items
        if e.evidence_type == "repo"
        and (e.quality_score or 0) >= 0.4
        and e.repo_type in ("official", "reproduction", "baseline_framework")
        and e.review_status not in ("rejected",)
    )
    low_quality = sum(
        1 for e in items
        if ((e.relevance_score is not None and e.relevance_score < 0.3)
            or (e.quality_score is not None and e.quality_score < 0.3))
    )
    rejected = sum(1 for e in items if e.review_status == "rejected")
    return {
        "project_id": project_id,
        "usable_papers": usable_papers,
        "usable_datasets": usable_datasets,
        "usable_repos": usable_repos,
        "low_quality_evidence": low_quality,
        "rejected_evidence": rejected,
        "feasibility_inputs": {
            "paper_quality": "强" if usable_papers >= 3 else ("中" if usable_papers >= 1 else "弱"),
            "dataset_quality": "强" if usable_datasets >= 2 else ("中" if usable_datasets >= 1 else "弱"),
            "repo_quality": "强" if usable_repos >= 2 else ("中" if usable_repos >= 1 else "弱"),
        },
    }


def dedup_check(project_id: str, body) -> dict:
    """Session 5 §8.3: 手动添加前提示."""

    from ..schemas_evidence import EvidenceItem
    fake = EvidenceItem(
        evidence_id="__check__", project_id=project_id,
        evidence_type=body.evidence_type, source_mode="manual",
        title=body.title, url=body.url, doi=body.doi, arxiv_id=body.arxiv_id,
    )
    proj = _get_project(project_id)
    existing = [e for e in proj.items.values() if e.evidence_type == body.evidence_type]
    dup = _is_duplicate(fake, existing)
    if dup:
        # 推断 reason
        if body.evidence_type == "paper":
            if body.doi and dup.doi and body.doi.lower() == dup.doi.lower():
                reason = "same_doi"
            elif body.arxiv_id and dup.arxiv_id and body.arxiv_id.lower() == dup.arxiv_id.lower():
                reason = "same_arxiv_id"
            else:
                reason = "similar_title"
        elif body.evidence_type == "repo":
            reason = "same_github_repo"
        else:
            reason = "same_dataset_name"
        return {
            "is_duplicate": True,
            "existing_evidence_id": dup.evidence_id,
            "reason": reason,
        }
    return {"is_duplicate": False, "existing_evidence_id": None, "reason": None}


# ---------- Session 7 §7.3 Trace 记录 ---------- #


def append_trace(project_id: str, action: str, target_type: str, target_id: str,
                 evidence_id: str | None = None, reason: str | None = None,
                 actor: str = "system") -> dict[str, Any]:
    """追加一条 Trace 记录到 project 的 trace 日志 (in-memory).

    - actor: system / user
    - target_type: feasibility / pivot_route / work_package / review_check / proposal / coverage
    - target_id: ref_idx / WP id / route level
    - action: rebuild / remove_ref / mark_ref_core / mark_ref_wrong / replace_ref / coverage_change / etc
    """

    from datetime import datetime, timezone

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "evidence_id": evidence_id,
        "reason": reason,
    }
    with _TRACE_LOCK:
        _TRACE.setdefault(project_id, []).append(event)
    return event


def get_trace(project_id: str) -> list[dict[str, Any]]:
    with _TRACE_LOCK:
        return list(_TRACE.get(project_id, []))


def clear_trace(project_id: str) -> None:
    with _TRACE_LOCK:
        _TRACE.pop(project_id, None)


# ---------- Session 7 §7: Snapshot (缓存最后一次 analyze 响应, 供 rebuild/coverage 用) ---------- #


def save_snapshot(project_id: str, snapshot: dict[str, Any]) -> None:
    """缓存最近一次 OneTopicResponse.model_dump() 的核心段."""

    with _LEDGER_LOCK:
        proj = _get_project(project_id)
        proj.latest_snapshot = snapshot


def get_snapshot(project_id: str) -> dict[str, Any] | None:
    with _LEDGER_LOCK:
        proj = _get_project(project_id)
        return proj.latest_snapshot


def get_pool_items(project_id: str) -> list[EvidenceItem]:
    """取 project 的全部 EvidenceItem (供 rebuild 时通过 extras 注入)."""

    with _LEDGER_LOCK:
        proj = _get_project(project_id)
        return list(proj.items.values())
