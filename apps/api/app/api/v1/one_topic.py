"""OneTopic router: POST /analyze + POST /analyze/stream (SSE) + 证据工作台端点 (SOP 5).

对齐 Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md §12.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from ...schemas import OneTopicRequest, OneTopicResponse, ProposalRecommendation
from ...schemas import PivotRoute, FeasibilitySummary, LightReview, EvidenceRef
from ...schemas_evidence import (
    DatasetManualCreate,
    EvidenceActionResponse,
    EvidenceLedgerResponse,
    PaperManualCreate,
    RepoManualCreate,
    ReviewUpdate,
)
from ...services import evidence as ev_store
from ...services import evidence_refs as refs_service
from ...services import one_topic as ot_service

router = APIRouter(prefix="/api/v1/one-topic", tags=["one-topic"])


# ---------- Session 5: 评分 / 去重 端点的 Pydantic 模型 (§8) ---------- #


class RescoreResponse(BaseModel):
    """POST /evidence/rescore  响应."""

    project_id: str
    paper_count: int
    dataset_count: int
    repo_count: int
    updated_count: int
    summary: dict


class ScoreSummaryResponse(BaseModel):
    """GET /evidence/score-summary  响应."""

    project_id: str
    usable_papers: int
    usable_datasets: int
    usable_repos: int
    low_quality_evidence: int
    rejected_evidence: int
    feasibility_inputs: dict


class DedupCheckRequest(BaseModel):
    """POST /evidence/dedup/check  请求体."""

    model_config = ConfigDict(extra="forbid")

    evidence_type: Literal["paper", "dataset", "repo"]
    title: str = Field(min_length=1)
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None


class DedupCheckResponse(BaseModel):
    """POST /evidence/dedup/check  响应."""

    is_duplicate: bool
    existing_evidence_id: str | None = None
    reason: str | None = None


# ---------- Session 7: EvidenceRef 复核 端点的 Pydantic 模型 (§7) ---------- #


class RefsRebuildResponse(BaseModel):
    """POST /evidence/refs/rebuild  响应."""

    project_id: str
    feasibility_refs_count: int
    pivot_routes_with_refs: int
    work_packages_with_refs: int
    review_checks_with_refs: int
    coverage_score: float
    message: str = "evidence_refs 已重建, review_status 未变"


class RefsCoverageResponse(BaseModel):
    """GET /evidence/refs/coverage  响应 (SOP §7.2)."""

    project_id: str
    feasibility_has_refs: bool
    pivot_routes_with_refs: int
    pivot_routes_total: int
    work_packages_with_refs: int
    work_packages_total: int
    review_checks_with_refs: int
    review_checks_total: int
    topic_evidence_refs_count: int
    unsupported_claims: list[str] = Field(default_factory=list)
    coverage_score: float
    low_coverage_warning: bool = False


class RefsReviewRequest(BaseModel):
    """PATCH /evidence/refs/review  请求体 (SOP §7.3)."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["feasibility", "pivot_route", "work_package", "review_check", "proposal"]
    target_id: str = Field(min_length=1, description="可行性无 idx; pivot = level; WP = wp_id; review = dimension; proposal = reason_key")
    evidence_id: str = Field(min_length=1, description="要操作的 evidence_id")
    action: Literal["add_ref", "remove_ref", "mark_ref_core", "mark_ref_wrong", "replace_ref"]
    reason: str | None = Field(default=None, description="用户复核理由 (会写入 Trace)")
    replacement_evidence_id: str | None = Field(default=None, description="replace_ref 时新 evidence_id")


class RefsReviewResponse(BaseModel):
    """PATCH /evidence/refs/review  响应."""

    project_id: str
    ok: bool
    target_type: str
    target_id: str
    evidence_id: str
    action: str
    trace_event: dict
    new_coverage_score: float
    message: str = ""


# ---------- 一题分析 ---------- #


@router.post("/analyze", response_model=OneTopicResponse, summary="一题分析: 6 段产物一次返回")
def analyze(req: OneTopicRequest) -> OneTopicResponse:
    try:
        return ot_service.run_one_topic(req)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc


@router.post("/analyze/stream", summary="一题分析 SSE 流式: 边推 trace 边算")
async def analyze_stream(req: OneTopicRequest) -> StreamingResponse:
    """SSE 端点. 事件流:
    start / step (keyword_decompose / paper_search / dataset_search / engineering_search /
                  feasibility / proposal_recommendation / light_review / result) / warn / error / end.
    """

    async def _gen() -> AsyncGenerator[bytes, None]:
        queue: asyncio.Queue = asyncio.Queue()

        def emit(name: str, detail: str, meta: dict | None = None) -> None:
            payload = {
                "type": (
                    "result" if name == "result" else
                    "error" if name == "error" else
                    "warn" if name == "warn" else
                    "start" if name == "start" else
                    "step"
                ),
                "name": name,
                "detail": detail,
                "meta": meta or {},
            }
            queue.put_nowait(payload)

        yield "data: " + json.dumps({"type": "start", "phase": "one_topic"}, ensure_ascii=False) + "\n\n"

        async def _run() -> None:
            try:
                await asyncio.to_thread(ot_service.run_one_topic_stream, req, emit)
            except Exception as exc:  # noqa: BLE001
                emit("error", f"{type(exc).__name__}: {exc}")
            finally:
                await queue.put({"type": "__end__"})

        task = asyncio.create_task(_run())

        while True:
            ev = await queue.get()
            if ev.get("type") == "__end__":
                break
            yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"

        await task
        yield "data: " + json.dumps({"type": "end"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 证据工作台 (SOP 5 + 13.1) ---------- #


@router.post(
    "/{project_id}/regenerate",
    response_model=OneTopicResponse,
    summary="POST: 用用户编辑的 keywords / 检索计划复跑 (Session 3 Gate 1+2)",
)
def regenerate(project_id: str, req: OneTopicRequest) -> OneTopicResponse:
    """Gate 1+2 用户编辑后复跑.

    - 清掉所有 auto_* 证据 (保留手动 man_*)
    - 用 url 的 project_id 覆盖, 沿用同一个 evidence ledger
    - 如果 req.confirmed_keywords 给定, 跳过自动拆解
    - 如果 req.confirmed_search_plan 给定, 跳过自动 build_search_plan
    """

    ev_store.clear_auto_evidence(project_id)
    # 沿用 url 的 project_id
    req2 = req.model_copy(update={"project_id_override": project_id})
    return ot_service.run_one_topic(req2)


@router.post(
    "/{project_id}/pivot/select",
    response_model=ProposalRecommendation,
    summary="POST: 用户选了 1 条 pivot 路线后, 生成对应工作包 (Session 4)",
)
def select_pivot_route(project_id: str, body: PivotRoute) -> ProposalRecommendation:
    """§10.4 用户选 1 条路线 (conservative/balanced/aggressive) 后生成对应工作包.

    - 用已有的 keyword_breakdown + evidence_summary 重建 ProposalRecommendation
    - 沿用 project_id (确保 evidence ledger 一致)
    - 返回的 work_packages / recommended_topic 来自 pivot 路线
    """

    # 取当前 project 的 evidence ledger + 上次跑出的 keywords (用最新一次 analyze 的结果)
    ledger = ev_store.get_ledger(project_id)
    if not ledger.papers and not ledger.datasets and not ledger.repos:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有任何证据, 请先 POST /analyze 或 /regenerate",
        )

    # 从 evidence-ledger 推断 keywords (heuristic fallback: 用前一次 analyze 留下的 paper titles 拼)
    paper_titles = [p.title for p in ledger.papers if p.title][:5]
    keywords = ot_service.KeywordBreakdown(
        method_keywords=[t.split()[0] for t in paper_titles if t] or ["深度学习方法"],
        task_keywords=["目标检测"],
        object_keywords=[paper_titles[0].split(" ")[-1] if paper_titles else "目标对象"],
        scenario_keywords=[],
        metric_keywords=["mAP", "Recall"],
        risk_terms=[],
        query_keywords_zh=[], query_keywords_en=[],
    )
    # 构造 EvidenceSummary 来自 ledger
    ev = ot_service.EvidenceSummary(
        papers=[ot_service.PaperHit(paper_id=p.evidence_id, title=p.title) for p in ledger.papers],
        datasets=[ot_service.DatasetHit(dataset_id=d.evidence_id, name=d.title) for d in ledger.datasets],
        baselines=[ot_service.BaselineHit(baseline_id=r.evidence_id, name=r.title) for r in ledger.repos],
        metrics=["mAP", "Recall", "FPS"],
        paper_count=len(ledger.papers),
        arxiv_paper_count=sum(1 for p in ledger.papers if (p.tags or []) and "auto" in p.tags),
        dataset_count=len(ledger.datasets),
        baseline_count=len(ledger.repos),
        has_public_dataset=len(ledger.datasets) > 0,
        has_repro_baseline=len(ledger.repos) > 0,
        has_metrics=True,
    )
    return ot_service.apply_pivot_route(
        route=body,
        keywords=keywords,
        ev=ev,
    )


@router.get(
    "/{project_id}/evidence",
    response_model=EvidenceLedgerResponse,
    summary="GET: 取一个 project 的证据池 (含自动入池 + 手动添加的)",
)
def get_evidence(project_id: str) -> EvidenceLedgerResponse:
    return ev_store.get_ledger(project_id)


@router.post(
    "/{project_id}/evidence/papers/manual",
    response_model=EvidenceActionResponse,
    summary="POST: 手动添加一篇论文 (DOI / arXiv / 标题去重)",
)
def add_paper_manual(project_id: str, body: PaperManualCreate) -> EvidenceActionResponse:
    return ev_store.add_paper_manual(project_id, body)


@router.post(
    "/{project_id}/evidence/datasets/manual",
    response_model=EvidenceActionResponse,
    summary="POST: 手动添加一个数据集",
)
def add_dataset_manual(project_id: str, body: DatasetManualCreate) -> EvidenceActionResponse:
    return ev_store.add_dataset_manual(project_id, body)


@router.post(
    "/{project_id}/evidence/repos/manual",
    response_model=EvidenceActionResponse,
    summary="POST: 手动添加一个 GitHub 工程",
)
def add_repo_manual(project_id: str, body: RepoManualCreate) -> EvidenceActionResponse:
    return ev_store.add_repo_manual(project_id, body)


@router.patch(
    "/evidence/{evidence_id}/review",
    response_model=EvidenceActionResponse,
    summary="PATCH: 更新单条证据的 review_status (accepted / core / background / rejected / needs_check)",
)
def update_review(evidence_id: str, body: ReviewUpdate) -> EvidenceActionResponse:
    return ev_store.update_review(evidence_id, body)


@router.delete(
    "/evidence/{evidence_id}",
    response_model=EvidenceActionResponse,
    summary="DELETE: 删除一条证据",
)
def delete_evidence(evidence_id: str) -> EvidenceActionResponse:
    return ev_store.delete_evidence(evidence_id)


# ---------- Session 5: 评分 / 去重 端点 (§8) ---------- #


@router.post(
    "/{project_id}/evidence/rescore",
    response_model=RescoreResponse,
    summary="Session 5 §8.1: 重新评分 (不改变 review_status)",
)
def rescore_evidence(project_id: str) -> RescoreResponse:
    """对当前 project 的 evidence pool 重新计算 score / paper_type / dataset_status / repo_type.

    不改变 user review_status. 被 rejected 的证据仍保留, 但不参与可行性判断.
    """

    return ev_store.rescore_project(project_id)


@router.get(
    "/{project_id}/evidence/score-summary",
    response_model=ScoreSummaryResponse,
    summary="Session 5 §8.2: 评分摘要 (含 feasibility 喂入的统计)",
)
def score_summary(project_id: str) -> ScoreSummaryResponse:
    return ev_store.score_summary(project_id)


@router.post(
    "/{project_id}/evidence/dedup/check",
    response_model=DedupCheckResponse,
    summary="Session 5 §8.3: 去重检查 (手动添加前提示)",
)
def dedup_check(project_id: str, body: DedupCheckRequest) -> DedupCheckResponse:
    return ev_store.dedup_check(project_id, body)


# ---------- Session 7: EvidenceRef 复核 端点 (§7) ---------- #


def _hydrate_snapshot(project_id: str) -> tuple[FeasibilitySummary, ProposalRecommendation, LightReview, list, list, list]:
    """从 snapshot 还原 4 个对象 + papers/datasets/baselines 原始 list."""

    snap = ev_store.get_snapshot(project_id)
    if not snap:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有快照, 请先 POST /analyze",
        )

    feas = FeasibilitySummary.model_validate(snap["feasibility"])
    rec = ProposalRecommendation.model_validate(snap["proposal_recommendation"])
    rev = LightReview.model_validate(snap["light_review"])
    ev_sum = snap.get("evidence_summary", {})
    return (
        feas, rec, rev,
        ev_sum.get("papers", []),
        ev_sum.get("datasets", []),
        ev_sum.get("baselines", []),
    )


def _extras_pool(project_id: str) -> list[dict]:
    """从 evidence ledger 拉 extras (手动入池, 含 review_status)."""

    pool = ev_store.get_pool_items(project_id)
    return [p.model_dump() for p in pool]


def _rebuild_all_refs(project_id: str) -> tuple[FeasibilitySummary, ProposalRecommendation, LightReview, list[str]]:
    """重建所有层的 evidence_refs. 不改变 review_status, 不删证据."""

    feas, rec, rev, papers, datasets, baselines = _hydrate_snapshot(project_id)
    extras = _extras_pool(project_id)

    # Feasibility
    feas = refs_service.build_feasibility_refs(
        feas, papers, datasets, baselines, extras=extras, project_id=project_id,
    )

    # PivotRoute × 3
    new_pivots = []
    for route in rec.pivot_routes:
        new_pivots.append(
            refs_service.build_pivot_refs(
                route, papers, datasets, baselines, extras=extras, project_id=project_id,
            )
        )
    rec.pivot_routes = new_pivots

    # WorkPackage × N
    new_wps = []
    for wp in rec.work_packages:
        new_wps.append(
            refs_service.build_wp_refs(
                wp, papers, datasets, baselines, extras=extras, project_id=project_id,
            )
        )
    rec.work_packages = new_wps

    # ProposalRecommendation 顶层
    rec, unsupported = refs_service.build_proposal_refs(
        rec, papers, datasets, baselines, extras=extras, project_id=project_id,
    )

    # LightReview 5 维
    rev = refs_service.build_review_refs(
        rev, papers, datasets, baselines, extras=extras, project_id=project_id,
    )

    # 写回 snapshot (供后续 /coverage 调用)
    snap = ev_store.get_snapshot(project_id)
    if snap:
        snap["feasibility"] = feas.model_dump(mode="json")
        snap["proposal_recommendation"] = rec.model_dump(mode="json")
        snap["light_review"] = rev.model_dump(mode="json")
        ev_store.save_snapshot(project_id, snap)

    return feas, rec, rev, unsupported


@router.post(
    "/{project_id}/evidence/refs/rebuild",
    response_model=RefsRebuildResponse,
    summary="Session 7 §7.1: 重建 evidence_refs (不改变 review_status)",
)
def rebuild_refs(project_id: str) -> RefsRebuildResponse:
    feas, rec, rev, _ = _rebuild_all_refs(project_id)
    coverage = refs_service.coverage_score(feas, rec)

    ev_store.append_trace(
        project_id, "rebuild", "feasibility", "all",
        reason="POST /evidence/refs/rebuild 调用",
    )

    pivot_with = sum(1 for p in rec.pivot_routes if p.evidence_refs)
    wp_with = sum(1 for w in rec.work_packages if w.evidence_refs)
    rev_with = sum(1 for c in rev.checks if c.evidence_refs)

    return RefsRebuildResponse(
        project_id=project_id,
        feasibility_refs_count=len(feas.evidence_refs),
        pivot_routes_with_refs=pivot_with,
        work_packages_with_refs=wp_with,
        review_checks_with_refs=rev_with,
        coverage_score=coverage,
    )


@router.get(
    "/{project_id}/evidence/refs/coverage",
    response_model=RefsCoverageResponse,
    summary="Session 7 §7.2: 证据覆盖率摘要 (含 unsupported_claims)",
)
def coverage_refs(project_id: str) -> RefsCoverageResponse:
    feas, rec, rev, unsupported = _rebuild_all_refs(project_id)
    coverage = refs_service.coverage_score(feas, rec)
    return RefsCoverageResponse(
        project_id=project_id,
        feasibility_has_refs=bool(feas.evidence_refs),
        pivot_routes_with_refs=sum(1 for p in rec.pivot_routes if p.evidence_refs),
        pivot_routes_total=len(rec.pivot_routes),
        work_packages_with_refs=sum(1 for w in rec.work_packages if w.evidence_refs),
        work_packages_total=len(rec.work_packages),
        review_checks_with_refs=sum(1 for c in rev.checks if c.evidence_refs),
        review_checks_total=len(rev.checks),
        topic_evidence_refs_count=len(rec.topic_evidence_refs),
        unsupported_claims=unsupported,
        coverage_score=coverage,
        low_coverage_warning=coverage < 0.70,
    )


def _apply_ref_action(target_list: list[EvidenceRef], body: RefsReviewRequest) -> bool:
    """应用 remove_ref / mark_ref_core / mark_ref_wrong / replace_ref / add_ref 到 ref list.

    Returns: 是否成功.
    """

    if body.action == "remove_ref":
        before = len(target_list)
        target_list[:] = [r for r in target_list if r.evidence_id != body.evidence_id]
        return len(target_list) < before

    if body.action == "mark_ref_core":
        # 触发 extras 的 review_status 升级 (通过 ev_store)
        for r in target_list:
            if r.evidence_id == body.evidence_id:
                r.review_status = "core"
                return True
        return False

    if body.action == "mark_ref_wrong":
        for r in target_list:
            if r.evidence_id == body.evidence_id:
                r.review_status = "rejected"
                r.role = "alternative"
                return True
        return False

    if body.action == "add_ref":
        # 用户 add_ref: 直接从 ledger 拉 evidence_item 拼成 ref
        pool = ev_store.get_pool_items("")  # placeholder; caller 会传 project
        return False  # 由 endpoint 处理

    if body.action == "replace_ref":
        before = len(target_list)
        target_list[:] = [r for r in target_list if r.evidence_id != body.evidence_id]
        if not body.replacement_evidence_id:
            return False
        # 拉新 ref
        pool = ev_store.get_pool_items("")
        return False  # 由 endpoint 处理

    return False


def _find_target_refs(project_id: str, target_type: str, target_id: str) -> list[EvidenceRef]:
    """从 snapshot 找到对应的 ref list. 失败抛 409."""

    snap = ev_store.get_snapshot(project_id)
    if not snap:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有快照, 请先 POST /analyze",
        )

    if target_type == "feasibility":
        return [r.model_copy() for r in FeasibilitySummary.model_validate(snap["feasibility"]).evidence_refs]
    if target_type == "pivot_route":
        rec = ProposalRecommendation.model_validate(snap["proposal_recommendation"])
        for route in rec.pivot_routes:
            if route.level == target_id:
                return [r.model_copy() for r in route.evidence_refs]
        raise HTTPException(status_code=404, detail=f"pivot_route {target_id} 不存在")
    if target_type == "work_package":
        rec = ProposalRecommendation.model_validate(snap["proposal_recommendation"])
        for wp in rec.work_packages:
            if wp.wp_id == target_id:
                return [r.model_copy() for r in wp.evidence_refs]
        raise HTTPException(status_code=404, detail=f"work_package {target_id} 不存在")
    if target_type == "review_check":
        rev = LightReview.model_validate(snap["light_review"])
        for c in rev.checks:
            if c.dimension == target_id:
                return [r.model_copy() for r in c.evidence_refs]
        raise HTTPException(status_code=404, detail=f"review_check {target_id} 不存在")
    raise HTTPException(status_code=400, detail=f"target_type {target_type} 不支持")


def _write_target_refs(project_id: str, target_type: str, target_id: str, new_refs: list[EvidenceRef]) -> None:
    """把改后的 ref list 写回 snapshot."""

    snap = ev_store.get_snapshot(project_id)
    if not snap:
        return

    if target_type == "feasibility":
        feas = FeasibilitySummary.model_validate(snap["feasibility"])
        feas.evidence_refs = new_refs
        snap["feasibility"] = feas.model_dump(mode="json")
    elif target_type == "pivot_route":
        rec = ProposalRecommendation.model_validate(snap["proposal_recommendation"])
        for route in rec.pivot_routes:
            if route.level == target_id:
                route.evidence_refs = new_refs
                break
        snap["proposal_recommendation"] = rec.model_dump(mode="json")
    elif target_type == "work_package":
        rec = ProposalRecommendation.model_validate(snap["proposal_recommendation"])
        for wp in rec.work_packages:
            if wp.wp_id == target_id:
                wp.evidence_refs = new_refs
                break
        snap["proposal_recommendation"] = rec.model_dump(mode="json")
    elif target_type == "review_check":
        rev = LightReview.model_validate(snap["light_review"])
        for c in rev.checks:
            if c.dimension == target_id:
                c.evidence_refs = new_refs
                break
        snap["light_review"] = rev.model_dump(mode="json")

    ev_store.save_snapshot(project_id, snap)


def _resolve_ref_from_ledger(project_id: str, evidence_id: str) -> EvidenceRef | None:
    """从 ledger 拉 evidence_item, 拼成 EvidenceRef (供 add_ref / replace_ref 用)."""

    for item in ev_store.get_pool_items(project_id):
        if item.evidence_id == evidence_id:
            return EvidenceRef(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                title=item.title,
                role="supports",
                reason="用户手动添加引用",
                score=item.relevance_score or item.quality_score,
                review_status=item.review_status,
                url=item.url or item.repository_url or item.download,
                url_verified=bool(item.url or item.repository_url or item.download),
            )
    return None


@router.patch(
    "/{project_id}/evidence/refs/review",
    response_model=RefsReviewResponse,
    summary="Session 7 §7.3: 用户复核 EvidenceRef (add/remove/mark_core/mark_wrong/replace)",
)
def review_ref(project_id: str, body: RefsReviewRequest) -> RefsReviewResponse:
    new_refs = _find_target_refs(project_id, body.target_type, body.target_id)
    ok = True
    message = ""

    if body.action == "remove_ref":
        before = len(new_refs)
        new_refs[:] = [r for r in new_refs if r.evidence_id != body.evidence_id]
        ok = len(new_refs) < before
        if not ok:
            message = f"evidence_id {body.evidence_id} 不在当前 ref 列表"
    elif body.action == "mark_ref_core":
        found = False
        for r in new_refs:
            if r.evidence_id == body.evidence_id:
                r.review_status = "core"
                found = True
        ok = found
        if not found:
            message = f"evidence_id {body.evidence_id} 不在当前 ref 列表"
    elif body.action == "mark_ref_wrong":
        found = False
        for r in new_refs:
            if r.evidence_id == body.evidence_id:
                r.review_status = "rejected"
                r.role = "alternative"
                found = True
        ok = found
        if not found:
            message = f"evidence_id {body.evidence_id} 不在当前 ref 列表"
    elif body.action == "add_ref":
        new_ref = _resolve_ref_from_ledger(project_id, body.evidence_id)
        if not new_ref:
            ok = False
            message = f"evidence_id {body.evidence_id} 不在 ledger 中"
        else:
            new_refs.append(new_ref)
    elif body.action == "replace_ref":
        new_refs[:] = [r for r in new_refs if r.evidence_id != body.evidence_id]
        if not body.replacement_evidence_id:
            ok = False
            message = "replace_ref 必须给 replacement_evidence_id"
        else:
            new_ref = _resolve_ref_from_ledger(project_id, body.replacement_evidence_id)
            if not new_ref:
                ok = False
                message = f"replacement_evidence_id {body.replacement_evidence_id} 不在 ledger 中"
            else:
                new_refs.append(new_ref)
    else:
        ok = False
        message = f"未知 action: {body.action}"

    if ok:
        _write_target_refs(project_id, body.target_type, body.target_id, new_refs)

    trace_event = ev_store.append_trace(
        project_id, body.action, body.target_type, body.target_id,
        evidence_id=body.evidence_id,
        reason=body.reason,
        actor="user",
    )

    # 算新 coverage (直接从当前 snapshot 读, 避免 rebuild 覆盖用户改动)
    snap2 = ev_store.get_snapshot(project_id)
    if snap2:
        feas_now = FeasibilitySummary.model_validate(snap2["feasibility"])
        rec_now = ProposalRecommendation.model_validate(snap2["proposal_recommendation"])
        new_coverage = refs_service.coverage_score(feas_now, rec_now)
    else:
        new_coverage = 0.0

    return RefsReviewResponse(
        project_id=project_id,
        ok=ok,
        target_type=body.target_type,
        target_id=body.target_id,
        evidence_id=body.evidence_id,
        action=body.action,
        trace_event=trace_event,
        new_coverage_score=new_coverage,
        message=message or "ok",
    )
