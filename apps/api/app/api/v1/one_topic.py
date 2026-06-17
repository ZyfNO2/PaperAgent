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
from ...schemas import PivotRoute
from ...schemas_evidence import (
    DatasetManualCreate,
    EvidenceActionResponse,
    EvidenceLedgerResponse,
    PaperManualCreate,
    RepoManualCreate,
    ReviewUpdate,
)
from ...services import evidence as ev_store
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
