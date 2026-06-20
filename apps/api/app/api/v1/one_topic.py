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
from ...schemas import (
    FinalPackage,
    FinalPackageBuildOptions,
    FinalPackageSummary,
    WorkspaceBoardResponse,
    WorkspaceItemPatch,
    WorkspaceItemPatchResponse,
)
from ...schemas_evidence import (
    DatasetManualCreate,
    EvidenceActionResponse,
    EvidenceLedgerResponse,
    PaperManualCreate,
    RepoManualCreate,
    ReviewUpdate,
    VerificationBatchRequest,
    VerificationResult,
    VerificationSummary,
    ManualVerificationUpdate,
)
from ...services import evidence as ev_store
from ...services import evidence_refs as refs_service
from ...services import final_package as fp_service
from ...services import one_topic as ot_service
from ...services import workspace as ws_service
from ...services import card_intake as ci_service
from ...services import verification as ver_service
from ...services import trace_store as trace_service
from ...schemas_trace import (
    TraceEvent,
    TraceListResponse,
    TraceSummaryResponse,
    TraceTimelineResponse,
)
from ...schemas_quality import (
    ReportQualityReview,
    ReportReviewRequest,
    ReportReviewSummary,
)
from ...services import report_quality as quality_service
from ...services.retrieval import orchestrator as retrieval_service
from ...services import materials as materials_service
from ...schemas_retrieval import (
    RetrievalImportRequest,
    RetrievalImportResponse,
    RetrievalRun,
    RetrievalSearchRequest,
    RetrievalSummaryResponse,
)
from ...schemas_materials import (
    DraftCardUpdate,
    DraftEvidenceCard,
    MaterialBuildCardsRequest,
    MaterialImportRequest,
    MaterialImportResponse,
    MaterialItem,
    MaterialListResponse,
    MaterialTextRequest,
    MaterialUploadRequest,
    MaterialUploadResponse,
)

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


# ---------- Session 19: 开题报告模板 (default / engineering / cv_ai) ---------- #


class ReportTemplatesResponse(BaseModel):
    """GET /report/templates 响应."""

    templates: list[dict]
    default_key: str = "default"


@router.get(
    "/report/templates",
    response_model=ReportTemplatesResponse,
    summary="Session 19: 列出可用开题报告模板",
)
def list_report_templates() -> ReportTemplatesResponse:
    from ...services import report_templates as tmpl_service
    return ReportTemplatesResponse(
        templates=tmpl_service.list_templates(),
        default_key=tmpl_service.DEFAULT_TEMPLATE_KEY,
    )


# ---------- Session 8: FinalPackage Markdown 导出 (§5) ---------- #


@router.post(
    "/{project_id}/final-package/build",
    response_model=FinalPackage,
    summary="Session 8 §5.1: 从 snapshot 构建 FinalPackage (Markdown + sections + citations)",
)
def build_final_package(project_id: str, body: FinalPackageBuildOptions) -> FinalPackage:
    try:
        pkg = fp_service.build_final_package(project_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    ev_store.save_final_package(project_id, pkg)
    return pkg


@router.get(
    "/{project_id}/final-package",
    response_model=FinalPackageSummary,
    summary="Session 8 §5.3: 获取 FinalPackage 摘要 (不返回 markdown 全文)",
)
def get_final_package_summary(project_id: str) -> FinalPackageSummary:
    summary = fp_service.build_final_package_summary(project_id)
    if not summary:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有 FinalPackage, 请先 POST /final-package/build",
        )
    return summary


@router.get(
    "/{project_id}/final-package/markdown",
    summary="Session 8 §5.2: 下载 Markdown 文件 (Content-Type: text/markdown)",
)
def download_final_package_markdown(project_id: str):
    """若无缓存, 自动 build 一次 (MVP 行为)."""

    cached = ev_store.get_final_package(project_id)
    if cached is None:
        # 自动 build
        opts = FinalPackageBuildOptions()
        try:
            cached = fp_service.build_final_package(project_id, opts)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        ev_store.save_final_package(project_id, cached)

    md = cached.proposal_markdown
    filename = f"proposal_{project_id}.md"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "text/markdown; charset=utf-8",
        "Cache-Control": "no-store",
    }
    from fastapi.responses import Response
    return Response(content=md, media_type="text/markdown; charset=utf-8", headers=headers)


# ---------- Session 9: 双栏工作台 + Agent Card Intake (§4.3 + §4.4) ---------- #


class CardIntakeRequest(BaseModel):
    """POST /cards/intake 请求体 (§4.4)."""

    model_config = ConfigDict(extra="forbid")

    input_type: Literal["url", "text", "github", "dataset_page", "paper_page", "image", "pdf"] = "url"
    content: str = Field(min_length=1)
    hint: str | None = None
    target_lane: Literal["user_preferred", "system_found"] = "user_preferred"


class CardIntakeResponse(BaseModel):
    """POST /cards/intake 响应 (§4.4)."""

    ok: bool
    needs_user_confirmation: bool = True
    card_type: str
    evidence: dict = Field(default_factory=dict, description="EvidenceItem.model_dump()")
    extraction_confidence: float
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


@router.get(
    "/{project_id}/workspace/board",
    response_model=WorkspaceBoardResponse,
    summary="Session 9 §4.3: 双栏 Board (paper/dataset/repo 三类)",
)
def get_workspace_board(project_id: str) -> WorkspaceBoardResponse:
    boards = ws_service.get_workspace_board(project_id)
    return WorkspaceBoardResponse(
        project_id=project_id,
        papers=boards["paper"],
        datasets=boards["dataset"],
        repos=boards["repo"],
    )


@router.patch(
    "/{project_id}/workspace/item",
    response_model=WorkspaceItemPatchResponse,
    summary="Session 9 §4.3: 移动 / 标核心 / 拒绝 evidence (同步 review_status + 写 Trace)",
)
def patch_workspace_item(project_id: str, body: WorkspaceItemPatch) -> WorkspaceItemPatchResponse:
    return ws_service.patch_workspace_item(project_id, body)


@router.post(
    "/{project_id}/cards/intake",
    response_model=CardIntakeResponse,
    summary="Session 9 §4.4: Agent Card Intake 从 URL / 文字生成 pending EvidenceCard",
)
def cards_intake(project_id: str, body: CardIntakeRequest) -> CardIntakeResponse:
    item, card_type, confidence, warnings = ci_service.intake_card(
        project_id=project_id,
        input_type=body.input_type,
        content=body.content,
        hint=body.hint,
        target_lane=body.target_lane,
    )
    return CardIntakeResponse(
        ok=True,
        needs_user_confirmation=True,
        card_type=card_type,
        evidence=item.model_dump(mode="json"),
        extraction_confidence=confidence,
        warnings=warnings,
        message=f"已生成 {card_type} 卡片, 默认 pending 待用户确认",
    )


# ---------- Session 10: 多源轻验证与 URL Verified (§6) ---------- #


@router.post(
    "/{project_id}/evidence/{evidence_id}/verify",
    response_model=VerificationResult,
    summary="Session 10 §6.1: 验证单条证据 (URL / 元数据轻验证)",
)
def verify_one_evidence(project_id: str, evidence_id: str) -> VerificationResult:
    """对单条 evidence 跑验证. 更新 verification_* 字段, 不改变 review_status.

    返回 VerificationResult; 写入 Trace.
    """

    item = ev_store.get_item(evidence_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=f"evidence_id {evidence_id} 不在 project_id {project_id} 中",
        )

    result = ver_service.verify_evidence_item(item, refresh=True)
    updated = ver_service.apply_verification(item, result)
    ev_store.update_verification_field(evidence_id, updated)

    ev_store.append_trace(
        project_id, "verify_evidence", "evidence_item", evidence_id,
        evidence_id=evidence_id,
        reason=f"verification_status={result.verification_status}, source={result.verification_source}",
        actor="system",
    )
    return result


@router.post(
    "/{project_id}/evidence/verify",
    response_model=VerificationSummary,
    summary="Session 10 §6.2: 批量验证项目证据 (含 scope / refresh 选项)",
)
def verify_project_evidence(
    project_id: str, body: VerificationBatchRequest,
) -> VerificationSummary:
    """批量验证, 返回 VerificationSummary (含 high_risk_items)."""

    pool = ev_store.get_pool_items(project_id)
    if not pool:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有 evidence, 请先 POST /analyze 或手动添加",
        )

    results = ver_service.verify_project_evidence(
        project_id=project_id,
        pool_items=pool,
        scope=body.scope,
        include_rejected=body.include_rejected,
        include_pending=body.include_pending,
        refresh=body.refresh,
    )

    # 写回 ledger
    for r in results:
        item = ev_store.get_item(r.evidence_id)
        if item is None:
            continue
        # refresh=False 时跳过已验证条目, 不重写
        if not body.refresh and item.verification_status not in ("unverified",):
            continue
        updated = ver_service.apply_verification(item, r)
        ev_store.update_verification_field(r.evidence_id, updated)

    summary = ver_service.build_summary(project_id, results)

    ev_store.append_trace(
        project_id, "verify_project", "evidence_pool", body.scope,
        reason=f"verified={summary.verified}, partial={summary.partial}, failed={summary.failed}, skipped={summary.skipped}",
        actor="system",
    )
    return summary


@router.get(
    "/{project_id}/evidence/verification-summary",
    response_model=VerificationSummary,
    summary="Session 10 §6.3: 取项目验证摘要",
)
def verification_summary(project_id: str) -> VerificationSummary:
    pool = ev_store.get_pool_items(project_id)
    if not pool:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有 evidence",
        )

    # 不重跑, 用已有的 verification 字段聚合
    results: list[VerificationResult] = []
    for it in pool:
        # 包装 EvidenceItem 现有字段为 VerificationResult
        results.append(VerificationResult(
            evidence_id=it.evidence_id,
            evidence_type=it.evidence_type,
            ok=it.verification_status != "failed",
            url_verified=bool(it.url_verified),
            verification_status=it.verification_status,
            verification_confidence=it.verification_confidence or 0.0,
            verification_source=it.verification_source,
            normalized_url=it.url,
            metadata=it.verification_metadata,
            warnings=it.verification_warnings,
            checked_at=it.verification_checked_at.isoformat() if it.verification_checked_at else "",
        ))
    return ver_service.build_summary(project_id, results)


@router.patch(
    "/{project_id}/evidence/{evidence_id}/verification",
    response_model=VerificationResult,
    summary="Session 10 §6.4: 手动确认验证 (不改变 review_status, 写入 Trace)",
)
def manual_verification(
    project_id: str, evidence_id: str, body: ManualVerificationUpdate,
) -> VerificationResult:
    item = ev_store.get_item(evidence_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=f"evidence_id {evidence_id} 不在 project_id {project_id} 中",
        )

    now = ev_store._utcnow() if hasattr(ev_store, "_utcnow") else None
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)

    new_data = item.model_dump()
    new_data["verification_status"] = body.verification_status
    new_data["verification_source"] = body.verification_source
    if body.verification_confidence is not None:
        new_data["verification_confidence"] = body.verification_confidence
    else:
        # 手动确认的默认置信度
        new_data["verification_confidence"] = 0.90 if body.verification_status == "verified" else (
            0.20 if body.verification_status == "failed" else 0.50
        )
    new_data["url_verified"] = (body.verification_status == "verified")
    new_data["verification_checked_at"] = now
    new_data["verification_warnings"] = [body.reason] if body.reason else list(item.verification_warnings)
    new_data["verification_metadata"] = {**item.verification_metadata, "manual_reason": body.reason}

    updated = EvidenceItem(**new_data) if False else _reload_evidence(new_data)

    ev_store.update_verification_field(evidence_id, updated)

    ev_store.append_trace(
        project_id, "manual_verification", "evidence_item", evidence_id,
        evidence_id=evidence_id,
        reason=body.reason or f"manual: {body.verification_status} via {body.verification_source}",
        actor="user",
    )

    return VerificationResult(
        evidence_id=updated.evidence_id,
        evidence_type=updated.evidence_type,
        ok=updated.verification_status != "failed",
        url_verified=bool(updated.url_verified),
        verification_status=updated.verification_status,
        verification_confidence=updated.verification_confidence or 0.0,
        verification_source=updated.verification_source,
        normalized_url=updated.url,
        metadata=updated.verification_metadata,
        warnings=updated.verification_warnings,
        checked_at=updated.verification_checked_at.isoformat() if updated.verification_checked_at else now.isoformat(),
    )


def _reload_evidence(data: dict) -> "EvidenceItem":
    """用 dict 重建 EvidenceItem (避免循环 import)."""

    from ...schemas_evidence import EvidenceItem
    return EvidenceItem(**data)


# ---------- Session 11: Trace 持久化与操作回放 (§6) ---------- #


@router.get(
    "/{project_id}/trace",
    response_model=TraceListResponse,
    summary="Session 11 §6.1: 获取项目 Trace (按 action/actor/since 过滤)",
)
def get_project_trace(
    project_id: str,
    limit: int = 100,
    action: str | None = None,
    actor: str | None = None,
    since: str | None = None,
) -> TraceListResponse:
    return trace_service.get_trace(
        project_id=project_id,
        limit=limit,
        action=action,
        actor=actor,
        since=since,
    )


@router.get(
    "/{project_id}/trace/summary",
    response_model=TraceSummaryResponse,
    summary="Session 11 §6.3: Trace 摘要 (含 user/system 动作数和 key_decisions)",
)
def get_project_trace_summary(project_id: str) -> TraceSummaryResponse:
    return trace_service.get_trace_summary(project_id)


@router.get(
    "/{project_id}/evidence/{evidence_id}/timeline",
    response_model=TraceTimelineResponse,
    summary="Session 11 §6.2: 单条 evidence 的 timeline (按 evidence_id 过滤)",
)
def get_evidence_timeline(project_id: str, evidence_id: str) -> TraceTimelineResponse:
    events = trace_service.get_evidence_timeline(project_id, evidence_id)
    return TraceTimelineResponse(
        project_id=project_id,
        evidence_id=evidence_id,
        events=events,
    )


# ---------- Session 12: 报告质量检查与低门槛委员会复核 (§7) ---------- #


@router.post(
    "/{project_id}/report/review",
    response_model=ReportQualityReview,
    summary="Session 12 §7.1: 构建报告质量审核 (8 维, verdict 4 档)",
)
def build_report_review(project_id: str, body: ReportReviewRequest | None = None) -> ReportQualityReview:
    req = body or ReportReviewRequest()
    review = quality_service.build_quality_review(project_id, req)
    return review


@router.get(
    "/{project_id}/report/review",
    response_model=ReportReviewSummary,
    summary="Session 12 §7.2: 获取最近一次报告审核 (缩略)",
)
def get_report_review_summary(project_id: str) -> ReportReviewSummary:
    summary = quality_service.get_quality_review_summary(project_id)
    if not summary:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有 ReportQualityReview, 请先 POST /report/review",
        )
    return summary


@router.get(
    "/{project_id}/report/review/markdown",
    summary="Session 12 §7.3: 独立导出 ReportQualityReview Markdown",
)
def download_report_review_markdown(project_id: str):
    review = quality_service.get_quality_review(project_id)
    if not review:
        raise HTTPException(
            status_code=409,
            detail=f"project_id {project_id} 还没有 ReportQualityReview, 请先 POST /report/review",
        )
    md = quality_service.render_quality_markdown(review)
    filename = f"quality_review_{project_id}.md"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "text/markdown; charset=utf-8",
        "Cache-Control": "no-store",
    }
    from fastapi.responses import Response
    return Response(content=md, media_type="text/markdown; charset=utf-8", headers=headers)


# ---------- Session 14: 多源检索增强 (SOP §13) ---------- #


@router.post(
    "/{project_id}/retrieval/search",
    response_model=RetrievalRun,
    summary="Session 14: 多源检索",
)
async def run_retrieval_search(
    project_id: str,
    body: RetrievalSearchRequest,
) -> RetrievalRun:
    """按 SOP §13.1 启动一次多源检索.

    raw_topic 自动从 OneTopic project snapshot 中取, 允许 extra_keywords 补充.
    """

    snapshot = ev_store.get_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"project_id {project_id} 不存在 (未跑过 analyze)",
        )

    raw_topic = ""
    if snapshot.get("proposal_recommendation"):
        raw_topic = snapshot["proposal_recommendation"].get("recommended_topic") or ""
    if not raw_topic and snapshot.get("evidence_summary"):
        # 退一步: 用 evidence_summary 中已有论文标题组合
        pass
    if not raw_topic and not body.extra_keywords:
        raise HTTPException(
            status_code=422,
            detail="raw_topic 与 extra_keywords 都为空, 无法生成查询计划",
        )

    return await retrieval_service.run_retrieval(
        project_id=project_id,
        raw_topic=raw_topic,
        request=body,
    )


@router.get(
    "/{project_id}/retrieval/summary",
    response_model=RetrievalSummaryResponse,
    summary="Session 14: 检索摘要",
)
def get_retrieval_summary(project_id: str) -> RetrievalSummaryResponse:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    return retrieval_service.get_summary(project_id)


@router.post(
    "/{project_id}/retrieval/import",
    response_model=RetrievalImportResponse,
    summary="Session 14: 导入候选到 Evidence Ledger",
)
def run_retrieval_import(
    project_id: str,
    body: RetrievalImportRequest,
) -> RetrievalImportResponse:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    return retrieval_service.import_candidates(project_id, body)


# ---------- Session 15: 全文资料与图片 / PDF / 网页卡片化 (SOP §18) ---------- #


@router.post(
    "/{project_id}/materials/upload",
    response_model=MaterialUploadResponse,
    summary="Session 15: 上传 PDF / 图片等资料 (base64 JSON 形式)",
)
def upload_material(
    project_id: str,
    body: MaterialUploadRequest,
) -> MaterialUploadResponse:
    """接收 base64 上传, 保存 + 解析 + (可选) 生成草稿."""

    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    if not body.filename:
        raise HTTPException(status_code=422, detail="缺少 filename")
    try:
        import base64

        data = base64.b64decode(body.content_b64 or "", validate=True) if body.content_b64 else b""
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"base64 解码失败: {e}") from e
    if not data:
        raise HTTPException(status_code=422, detail="文件为空")
    result = materials_service.accept_upload(
        project_id,
        filename=body.filename,
        data=data,
        mime=body.mime,
        user_note=body.user_note,
        page_range=body.page_range,
        auto_build_cards=body.auto_build_cards,
        preferred_type=body.preferred_type,
        material_id=body.material_id,
    )
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return MaterialUploadResponse(
        material=result["material"],
        draft_cards=result["draft_cards"],
        message=result.get("message", ""),
    )


@router.post(
    "/{project_id}/materials/text",
    response_model=MaterialUploadResponse,
    summary="Session 15: 提交文本 / URL+描述 / 导师备注",
)
def submit_text_material(
    project_id: str,
    body: MaterialTextRequest,
) -> MaterialUploadResponse:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    result = materials_service.accept_text(project_id, body)
    return MaterialUploadResponse(
        material=result["material"],
        draft_cards=result["draft_cards"],
        message=result.get("message", ""),
    )


@router.get(
    "/{project_id}/materials",
    response_model=MaterialListResponse,
    summary="Session 15: 列出本项目所有 materials 与 drafts",
)
def list_project_materials(project_id: str) -> MaterialListResponse:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    data = materials_service.list_materials(project_id)
    return MaterialListResponse(
        project_id=project_id,
        materials=data["materials"],
        drafts=data["drafts"],
    )


@router.get(
    "/{project_id}/materials/{material_id}",
    response_model=MaterialItem,
    summary="Session 15: 单个 material",
)
def get_project_material(project_id: str, material_id: str) -> MaterialItem:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    m = materials_service.get_material(project_id, material_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"material {material_id} 不存在")
    return m


@router.post(
    "/{project_id}/materials/{material_id}/cards",
    response_model=list[DraftEvidenceCard],
    summary="Session 15: 显式生成草稿",
)
def build_project_draft_cards(
    project_id: str,
    material_id: str,
    body: MaterialBuildCardsRequest,
) -> list[DraftEvidenceCard]:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    return materials_service.build_draft_cards(project_id, material_id, body)


@router.patch(
    "/{project_id}/materials/cards/{draft_card_id}",
    response_model=DraftEvidenceCard,
    summary="Session 15: 编辑草稿",
)
def edit_project_draft_card(
    project_id: str,
    draft_card_id: str,
    body: DraftCardUpdate,
) -> DraftEvidenceCard:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    card = materials_service.edit_draft_card(project_id, draft_card_id, body)
    if card is None:
        raise HTTPException(status_code=404, detail=f"draft {draft_card_id} 不存在")
    return card


@router.post(
    "/{project_id}/materials/cards/import",
    response_model=MaterialImportResponse,
    summary="Session 15: 导入草稿到 Evidence Ledger",
)
def import_project_drafts(
    project_id: str,
    body: MaterialImportRequest,
) -> MaterialImportResponse:
    if ev_store.get_snapshot(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project_id {project_id} 不存在")
    return materials_service.import_drafts(project_id, body)


# ---------- Session 19: 报告模板元数据 (GET /report/templates) ---------- #


class ReportTemplateInfo(BaseModel):
    """单个模板的元数据 (供前端选择器展示)."""

    model_config = ConfigDict(extra="forbid")

    template_key: str
    name: str
    version: str
    applies_to: str
    required_sections: list[str] = Field(default_factory=list)
    evidence_required: bool = True
    placeholders: list[str] = Field(default_factory=list)


class ReportTemplatesResponse(BaseModel):
    """GET /report/templates 响应."""

    model_config = ConfigDict(extra="forbid")

    templates: list[dict] = Field(
        default_factory=list,
        description="模板元数据列表 (含 template_key / name / version / required_sections / ...)",
    )
    default_key: str = "default"


@router.get(
    "/report/templates",
    response_model=ReportTemplatesResponse,
    summary="Session 19: 列出全部开题报告模板元数据",
)
def list_report_templates() -> ReportTemplatesResponse:
    """前端模板选择控件用. 不依赖具体 project_id, 全局可用."""

    from ..services import report_templates as rt_service

    return ReportTemplatesResponse(
        templates=rt_service.list_templates(),
        default_key=rt_service.DEFAULT_TEMPLATE_KEY,
    )


# ---------- Session 27: RunEvent 持久化与回放 (SOP §2-5) ---------- #


from ...schemas_run_event import (
    RunCreateRequest,
    RunCreateResponse,
    RunEventAppendRequest,
    RunEventAppendResponse,
    RunEventListResponse,
    RunResumeRequest,
)
from ...services import run_event as re_service


@router.post(
    "/runs",
    response_model=RunCreateResponse,
    summary="S27: 创建新 run",
)
def create_run(body: RunCreateRequest) -> RunCreateResponse:
    return re_service.create_run(body)


@router.post(
    "/runs/{run_id}/events",
    response_model=RunEventAppendResponse,
    summary="S27: 追加事件到 run",
)
def append_run_event(run_id: str, body: RunEventAppendRequest) -> RunEventAppendResponse:
    """追加事件，project_id 从路径或 header 推断（这里用固定 proj_demo）."""
    project_id = "proj_demo"
    try:
        return re_service.append_event(project_id, run_id, body)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


@router.get(
    "/runs/{run_id}/events",
    response_model=RunEventListResponse,
    summary="S27: 获取 run 事件列表（支持重放）",
)
def get_run_events(run_id: str, from_seq: int = 0) -> RunEventListResponse:
    project_id = "proj_demo"
    try:
        return re_service.get_events(project_id, run_id, from_seq)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


@router.post(
    "/runs/{run_id}/resume",
    response_model=RunCreateResponse,
    summary="S27: 恢复 run（用户 patch + 策略）",
)
def resume_run(run_id: str, body: RunResumeRequest) -> RunCreateResponse:
    """恢复 run — 记录 user_patch，返回继续信息."""
    project_id = "proj_demo"
    try:
        re_service.append_user_patch(
            project_id, run_id, body.user_patch, body.from_seq, body.strategy
        )
        state = re_service.get_state(project_id, run_id)
        return RunCreateResponse(
            run_id=run_id,
            project_id=project_id,
            status=state.status,
            events_url=f"/api/v1/runs/{run_id}/events",
            stream_url=f"/api/v1/runs/{run_id}/stream",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


@router.post(
    "/runs/{run_id}/complete",
    response_model=RunCreateResponse,
    summary="S27: 标记 run 完成",
)
def complete_run(run_id: str, status: Literal["completed", "failed", "aborted"] = "completed") -> RunCreateResponse:
    project_id = "proj_demo"
    try:
        state = re_service.update_run_status(project_id, run_id, status)
        return RunCreateResponse(
            run_id=run_id,
            project_id=project_id,
            status=state.status,
            events_url=f"/api/v1/runs/{run_id}/events",
            stream_url=f"/api/v1/runs/{run_id}/stream",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


# ---------- Session 29: 开题报告草稿生成与证据绑定 (SOP §2-4) ---------- #


from ...schemas_proposal_draft import (
    ProposalDraft,
    ProposalDraftRequest,
)
from ...services.proposal_draft import generate_proposal_draft
from ...schemas_feasibility import FeasibilityAssessment


@router.post(
    "/proposal-draft",
    response_model=ProposalDraft,
    summary="S29: 生成开题报告草稿",
)
def create_proposal_draft(body: ProposalDraftRequest) -> ProposalDraft:
    return generate_proposal_draft(
        topic_title=body.topic_title,
        sections=body.sections,
        evidence_refs=body.evidence_refs,
        selected_refs=body.selected_refs,
        candidate_refs=body.candidate_refs,
        feasibility=body.feasibility,
    )


# ---------- Session 30: 委员会复核与 Revision Loop (SOP §2-4) ---------- #


from ...schemas_review import (
    ReviewRound,
    ReviewRequest,
    ReviewHistory,
    RevisionActionRequest,
)
from ...services.review import run_review, get_review_history, clear_review_history


@router.post(
    "/review",
    response_model=ReviewRound,
    summary="S30: 委员会复核",
)
def create_review(body: ReviewRequest) -> ReviewRound:
    return run_review(body)


@router.get(
    "/review/{topic_title}/history",
    response_model=ReviewHistory,
    summary="S30: 复核历史",
)
def review_history(topic_title: str) -> ReviewHistory:
    return get_review_history(topic_title)


# ---- S32: Export readiness ---- #

from ...schemas_readiness import ReadinessReport, ReadinessRequest
from ...services.readiness import check_readiness


@router.post(
    "/{project_id}/readiness",
    response_model=ReadinessReport,
    summary="S32: 导出前合规检查 (8 维 readiness)",
)
def check_export_readiness(project_id: str, body: ReadinessRequest) -> ReadinessReport:
    """Run 8-dimension readiness check on the project's final-package."""
    sections: list = []
    citations_raw: list = []
    proposal_md: str | None = None

    # 1) Try FinalPackage cache (has sections + citations + markdown)
    fp_cached = ev_store.get_final_package(project_id)
    if fp_cached is None:
        # Auto-build if snapshot exists
        snapshot = ev_store.get_snapshot(project_id)
        if snapshot:
            try:
                fp_cached = fp_service.build_final_package(
                    project_id, FinalPackageBuildOptions()
                )
                ev_store.save_final_package(project_id, fp_cached)
            except (ValueError, Exception):
                fp_cached = None

    if fp_cached:
        sections = [
            {"section_id": s.key, "content": s.content, "evidence_refs": [ref.evidence_id for ref in s.evidence_refs]}
            for s in fp_cached.sections
        ]
        citations_raw = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in fp_cached.citation_list
        ]
        proposal_md = fp_cached.proposal_markdown

    # 2) Fallback: snapshot proposal_recommendation
    if not sections:
        snapshot = ev_store.get_snapshot(project_id) or {}
        pr = snapshot.get("proposal_recommendation", {})
        outline = pr.get("proposal_outline", [])
        for item in outline:
            if isinstance(item, dict):
                sections.append(item)
            elif isinstance(item, str):
                sections.append({"section_id": item, "content": item})

    return check_readiness(
        sections=sections,
        citations=citations_raw,
        template_key=body.template_key,
        proposal_markdown=proposal_md,
        project_id=project_id,
    )
