"""Paper Library API (Session 46 + Session 47 + Session 48 + Session 49 + Session 50).

Session 46 4 端点:
- POST /api/v1/projects/{project_id}/paper-library/arxiv
- POST /api/v1/projects/{project_id}/paper-library/upload
- GET  /api/v1/projects/{project_id}/paper-library
- GET  /api/v1/projects/{project_id}/paper-library/{paper_id}

Session 47 新增 2 端点 (Paper RAG):
- POST /api/v1/projects/{project_id}/paper-library/{paper_id}/index
- POST /api/v1/projects/{project_id}/paper-library/ask

Session 48 新增 1 端点 (Claim Grounding):
- POST /api/v1/projects/{project_id}/paper-library/ground-claims

Session 49 新增 3 端点 (Track B: 已有小论文扩展):
- POST /api/v1/projects/{project_id}/paper-library/small-paper/extract
- POST /api/v1/projects/{project_id}/paper-library/small-paper/extension-plan
- POST /api/v1/projects/{project_id}/paper-library/small-paper/repeat-risks

Session 50 新增 4 端点 (RAG 评估与回归基线):
- POST /api/v1/projects/{project_id}/paper-library/eval/run
- GET  /api/v1/projects/{project_id}/paper-library/eval/baseline
- POST /api/v1/projects/{project_id}/paper-library/eval/baseline
- POST /api/v1/projects/{project_id}/paper-library/eval/seed-library
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...schemas_claim_grounding import (
    ClaimGroundBatchRequest,
    ClaimGroundBatchResponse,
    ClaimGroundingResult,
)
from ...schemas_paper_library import (
    ArxivIngestRequest,
    ArxivIngestResponse,
    LocalUploadIngestRequest,
    LocalUploadIngestResponse,
    PaperDetailChunkPreview,
    PaperDetailResponse,
    PaperListResponse,
)
from ...schemas_paper_rag import (
    PaperIndexRequest,
    PaperIndexResponse,
    PaperRAGAnswer,
    PaperRAGAskRequest,
)
from ...schemas_small_paper import (
    SmallPaperExtractRequest,
    SmallPaperExtractResponse,
    SmallPaperExtensionPlanRequest,
    SmallPaperExtensionPlanResponse,
    SmallPaperRepeatRisksRequest,
    SmallPaperRepeatRisksResponse,
)
from ...schemas_paper_rag_eval import (
    RagEvalRunRequest,
    RagEvalRunResponse,
    RagEvalSeedLibraryRequest,
    RagEvalSeedLibraryResponse,
)
from ...services import paper_library as pl_service
from ...services.paper_library import (
    claim_grounding,
    eval_baseline,
    indexer,
    paper_qa,
    rag_eval_pipeline,
    reranker,
    retriever,
)
from ...services.small_paper import (
    build_extension_plan,
    detect_repeat_risks,
    extract_small_paper_card,
)
from ...services.small_paper import chapter_mapper as sp_chapter_mapper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["paper-library"])


# ---------- arXiv ingest ---------- #


@router.post(
    "/{project_id}/paper-library/arxiv",
    response_model=ArxivIngestResponse,
)
def ingest_arxiv_paper(project_id: str, body: ArxivIngestRequest) -> ArxivIngestResponse:
    try:
        outcome = pl_service.ingest_arxiv(project_id, body.arxiv_id_or_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingest_arxiv failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"arXiv ingest failed: {exc}")

    return ArxivIngestResponse(
        paper_id=outcome.paper_id,
        status="duplicate" if outcome.is_duplicate else (
            "ingested" if outcome.parse_status in ("parsed", "skipped") else "failed"
        ),
        parse_status=outcome.parse_status,  # type: ignore[arg-type]
        chunk_count=outcome.chunk_count,
        evidence_id=outcome.evidence_id,
        is_duplicate=outcome.is_duplicate,
        message=outcome.message,
    )


# ---------- 本地 upload ---------- #


@router.post(
    "/{project_id}/paper-library/upload",
    response_model=LocalUploadIngestResponse,
)
def ingest_local_upload(project_id: str, body: LocalUploadIngestRequest) -> LocalUploadIngestResponse:
    try:
        outcome = pl_service.ingest_upload(
            project_id, body.filename, body.content_b64, body.mime,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingest_upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"upload ingest failed: {exc}")

    return LocalUploadIngestResponse(
        paper_id=outcome.paper_id,
        parse_status=outcome.parse_status,  # type: ignore[arg-type]
        chunk_count=outcome.chunk_count,
        evidence_id=outcome.evidence_id,
        is_duplicate=outcome.is_duplicate,
        message=outcome.message,
    )


# ---------- 列表 ---------- #


@router.get(
    "/{project_id}/paper-library",
    response_model=PaperListResponse,
)
def list_papers(project_id: str) -> PaperListResponse:
    papers = pl_service.list_papers(project_id)
    total_chunks = sum(p.chunk_count for p in papers)
    return PaperListResponse(
        project_id=project_id,
        papers=papers,
        total_chunks=total_chunks,
        total_papers=len(papers),
    )


# ---------- 详情 ---------- #


@router.get(
    "/{project_id}/paper-library/{paper_id}",
    response_model=PaperDetailResponse,
)
def get_paper_detail(project_id: str, paper_id: str) -> PaperDetailResponse:
    rec = pl_service.get_paper(project_id, paper_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"paper_id {paper_id} 不存在")
    chunks = pl_service.get_paper_chunks(project_id, paper_id)
    excerpt = pl_service.get_paper_text_excerpt(project_id, paper_id)

    previews: list[PaperDetailChunkPreview] = []
    for c in chunks[:3]:
        previews.append(PaperDetailChunkPreview(
            chunk_id=c.chunk_id,
            section_title=c.section_title,
            section_path=c.section_path,
            chunk_type=c.chunk_type,
            token_count=c.token_count,
            text_preview=(c.text or "")[:200],
        ))

    return PaperDetailResponse(
        paper=rec,
        chunks=previews,
        full_text_excerpt=excerpt[:1500] if excerpt else "",
        chunk_total=len(chunks),
    )


# ===========================================================================
# Session 47: Paper RAG — Index + Ask
# ===========================================================================


@router.post(
    "/{project_id}/paper-library/{paper_id}/index",
    response_model=PaperIndexResponse,
)
def index_paper(project_id: str, paper_id: str, body: PaperIndexRequest | None = None) -> PaperIndexResponse:
    """为指定 paper (或整个 project) 建 embedding 索引.

    body.force=true 时强制重建 (忽略已索引).
    """

    force = bool(body.force) if body else False
    try:
        result = indexer.build_index(project_id, paper_ids=[paper_id], force=force)
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_index failed for %s: %s", paper_id, exc)
        raise HTTPException(status_code=500, detail=f"index failed: {exc}")
    return PaperIndexResponse(
        paper_id=paper_id,
        chunk_count=int(result.get("chunk_count", 0)),
        indexed=int(result.get("indexed", 0)),
        skipped=int(result.get("skipped", 0)),
        duration_ms=int(result.get("duration_ms", 0)),
    )


@router.post(
    "/{project_id}/paper-library/ask",
    response_model=PaperRAGAnswer,
)
def ask_paper_library(project_id: str, body: PaperRAGAskRequest) -> PaperRAGAnswer:
    """Paper RAG 问答: query rewrite → retrieve → rerank → LLM → answer.

    LLM 失败: 自动 fallback (retrieval_mode=fallback, confidence=0).
    无命中: 明说"未在论文库中找到证据".
    """

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    # 1) 检索
    try:
        hits = retriever.retrieve(
            project_id=project_id,
            question=question,
            scope=body.scope,
            paper_ids=body.paper_ids,
            top_k=body.top_k,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("retrieve failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"retrieve failed: {exc}")

    idx = indexer.load_index(project_id)
    chunks_index = idx.get("chunks", {})

    # 2) 还原 chunk 元数据 + 计算 paper year lookup
    raw_chunks: list[dict] = []
    paper_year_lookup: dict[str, int | None] = {}
    for cid, _score in hits:
        meta = chunks_index.get(cid)
        if not meta:
            continue
        meta = dict(meta)
        meta["chunk_id"] = cid
        raw_chunks.append(meta)
        pid = meta.get("paper_id")
        if pid and pid not in paper_year_lookup:
            rec = pl_service.get_paper(project_id, pid)
            paper_year_lookup[pid] = rec.year if rec else None

    # 3) reranker
    reranked = reranker.rerank_chunks(
        question,
        [(meta, 0.0) for meta in raw_chunks],
        paper_year_lookup=paper_year_lookup,
    )
    top_chunks = [meta for meta, _ in reranked[: body.top_k]]

    if not top_chunks:
        # 无命中: 返回 no-hit answer
        from ...schemas_paper_rag import PaperRAGAnswer as _Answer
        return _Answer(
            question=question,
            answer="未在论文库中找到证据，无法回答该问题。",
            evidence_refs=[],
            unsupported_claims=[],
            confidence=0.0,
            used_papers=[],
            retrieval_mode="llm",  # type: ignore[arg-type]
        )

    # 4) 加载 paper titles 供 context
    used_paper_ids = sorted({c.get("paper_id", "") for c in top_chunks if c.get("paper_id")})
    paper_titles = paper_qa.load_paper_titles(project_id, used_paper_ids)

    # 5) LLM 问答 (失败 → fallback)
    try:
        answer = paper_qa.answer_with_llm(question, top_chunks, paper_titles=paper_titles)
    except Exception as exc:  # noqa: BLE001
        logger.info("paper_qa LLM fallback (reason=%s)", exc)
        answer = paper_qa.fallback_answer(question, top_chunks)

    # 5.5) Session 48 Task 2 + Task 6: 把 evidence_refs 写回 Evidence Ledger
    #       + 应用引用规则 (rejected 移除 / pending direct 降级 / failed 降级)
    try:
        # 引用规则
        filtered_refs, _warnings = paper_qa.filter_refs_by_citation_rules(project_id, answer.evidence_refs)
        answer = answer.model_copy(update={"evidence_refs": filtered_refs})
        # 写 ledger (chunk_id 去重, 失败不影响 answer)
        if filtered_refs:
            paper_qa.write_answer_to_ledger(project_id, answer)
    except Exception as exc:  # noqa: BLE001
        logger.info("paper_qa write-to-ledger failed (non-fatal): %s", exc)

    return answer


# ===========================================================================
# Session 48: Claim Grounding
# ===========================================================================


@router.post(
    "/{project_id}/paper-library/ground-claims",
    response_model=ClaimGroundBatchResponse,
)
def ground_claims(project_id: str, body: ClaimGroundBatchRequest) -> ClaimGroundBatchResponse:
    """对一批 report claim 调 ground_claim, 返回 grounding 判定.

    body: { claims: [...], scope?, paper_ids?, top_k? }
    resp: { results: ClaimGroundingResult[], total }
    """

    if not body.claims:
        raise HTTPException(status_code=400, detail="claims 不能为空")
    results: list[ClaimGroundingResult] = []
    for claim in body.claims:
        c = (claim or "").strip()
        if not c:
            continue
        try:
            r = claim_grounding.ground_claim(
                claim=c,
                project_id=project_id,
                scope=body.scope,
                paper_ids=body.paper_ids,
                top_k=body.top_k,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ground_claim failed for %r: %s", c[:60], exc)
            r = ClaimGroundingResult(
                claim=c, status="unsupported", verdict="unsupported",
                confidence=0.0, reason=f"ground_claim exception: {exc}",
                retrieval_mode="fallback",
            )
        results.append(r)
    return ClaimGroundBatchResponse(results=results, total=len(results))


# ===========================================================================
# Session 49: Track B — 已有小论文扩展 (SmallPaper → Thesis)
# ===========================================================================


@router.post(
    "/{project_id}/paper-library/small-paper/extract",
    response_model=SmallPaperExtractResponse,
)
def small_paper_extract(
    project_id: str, body: SmallPaperExtractRequest,
) -> SmallPaperExtractResponse:
    """抽小论文结构化卡片 (SmallPaperCard).

    body: { paper_id, prefer?: auto | llm | heuristic }
    resp: { paper_id, card, extraction_mode, extraction_confidence }

    404: paper_id 不存在
    500: 强制 LLM 但 LLM 不可用
    """

    try:
        card = extract_small_paper_card(
            project_id, body.paper_id, prefer=body.prefer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        # LLMUnavailable 在 prefer=llm 时透传
        from ...services.llm import LLMUnavailable as _LLMUnavail
        if isinstance(exc, _LLMUnavail):
            raise HTTPException(status_code=503, detail=f"LLM 不可用: {exc}")
        logger.warning("small_paper_extract failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"extract failed: {exc}")

    return SmallPaperExtractResponse(
        paper_id=card.paper_id,
        card=card,
        extraction_mode=card.extraction_mode,
        extraction_confidence=card.extraction_confidence,
    )


@router.post(
    "/{project_id}/paper-library/small-paper/extension-plan",
    response_model=SmallPaperExtensionPlanResponse,
)
def small_paper_extension_plan(
    project_id: str, body: SmallPaperExtensionPlanRequest,
) -> SmallPaperExtensionPlanResponse:
    """生成大论文扩展规划 (ExtensionPlan).

    body: { paper_id, target_chapter_count?: 5, prefer?: auto | heuristic }
    resp: { paper_id, plan }

    实现流程:
    1) extract_small_paper_card 拿 card
    2) chapter_mapper.map_chunks 拿 ChapterMapping 列表
    3) extension_planner.build_extension_plan 拿 plan
    4) repeat_risk.detect_repeat_risks → plan.reuse_risks

    404: paper_id 不存在
    """

    try:
        card = extract_small_paper_card(
            project_id, body.paper_id, prefer=body.prefer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        from ...services.llm import LLMUnavailable as _LLMUnavail
        if isinstance(exc, _LLMUnavail):
            raise HTTPException(status_code=503, detail=f"LLM 不可用: {exc}")
        logger.warning("small_paper_extract for plan failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"extract failed: {exc}")

    chunks = pl_service.get_paper_chunks(project_id, body.paper_id)
    mappings = sp_chapter_mapper.map_chapters(chunks)
    plan = build_extension_plan(
        card, mappings,
        paper_id=card.paper_id, project_id=project_id,
        target_chapter_count=body.target_chapter_count,
    )
    risks = detect_repeat_risks(card, plan, mappings)
    plan = plan.model_copy(update={"reuse_risks": [r.note for r in risks]})

    return SmallPaperExtensionPlanResponse(paper_id=card.paper_id, plan=plan)


@router.post(
    "/{project_id}/paper-library/small-paper/repeat-risks",
    response_model=SmallPaperRepeatRisksResponse,
)
def small_paper_repeat_risks(
    project_id: str, body: SmallPaperRepeatRisksRequest,
) -> SmallPaperRepeatRisksResponse:
    """检测小论文被原样塞进大论文的重复风险.

    body: { paper_id }
    resp: { paper_id, risks: list[RepeatRiskWarning], risk_count }
    """

    try:
        card = extract_small_paper_card(project_id, body.paper_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("small_paper_extract for risks failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"extract failed: {exc}")

    chunks = pl_service.get_paper_chunks(project_id, body.paper_id)
    mappings = sp_chapter_mapper.map_chapters(chunks)
    # 构造空 plan 供 risk 推断 (无 extension)
    from ...schemas_small_paper import ExtensionPlan as _EP
    skeleton = _EP(
        paper_id=card.paper_id, project_id=project_id,
        covered_chapters=[m.thesis_chapter for m in mappings],
        missing_chapters=[],
    )
    risks = detect_repeat_risks(card, skeleton, mappings)
    return SmallPaperRepeatRisksResponse(
        paper_id=card.paper_id, risks=risks, risk_count=len(risks),
    )


# ===========================================================================
# Session 50: RAG 评估与回归基线
# ===========================================================================


@router.post(
    "/{project_id}/paper-library/eval/seed-library",
    response_model=RagEvalSeedLibraryResponse,
)
def eval_seed_library(
    project_id: str, body: RagEvalSeedLibraryRequest | None = None,
) -> RagEvalSeedLibraryResponse:
    """把 fixtures 里的 txt 论文加载到 project storage (供 eval 测试用).

    body.fixtures_path 可选, 默认 tests/fixtures/paper_library_eval
    resp: { project_id, paper_count, chunk_count, message }
    """

    fixtures_path = body.fixtures_path if body else None
    fixtures_dir = Path(fixtures_path) if fixtures_path else _default_fixtures_dir()
    if not fixtures_dir.exists():
        raise HTTPException(status_code=400, detail=f"fixtures_dir 不存在: {fixtures_dir}")
    try:
        result = rag_eval_pipeline.seed_library_from_fixtures(project_id, fixtures_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("eval_seed_library failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"seed_library failed: {exc}")
    total_chunks = sum(result.values())
    return RagEvalSeedLibraryResponse(
        project_id=project_id,
        paper_count=len(result),
        chunk_count=total_chunks,
        message=f"loaded {len(result)} papers / {total_chunks} chunks from {fixtures_dir}",
    )


@router.post(
    "/{project_id}/paper-library/eval/run",
    response_model=RagEvalRunResponse,
)
def eval_run(
    project_id: str, body: RagEvalRunRequest | None = None,
) -> RagEvalRunResponse:
    """跑一次 RAG 评估, 产出 RagEvalReport.

    body: { fixtures_path?, scope?, paper_ids?, llm_mock? }
    resp: { report: RagEvalReport }

    400: fixtures_dir 不存在
    500: eval 失败
    """

    body = body or RagEvalRunRequest()
    fixtures_path = body.fixtures_path if body else None
    fixtures_dir = Path(fixtures_path) if fixtures_path else _default_fixtures_dir()
    if not fixtures_dir.exists():
        raise HTTPException(status_code=400, detail=f"fixtures_dir 不存在: {fixtures_dir}")
    try:
        report = rag_eval_pipeline.run_eval(
            project_id=project_id,
            fixtures_dir=fixtures_dir,
            scope=body.scope,
            paper_ids=body.paper_ids,
            llm_mock=body.llm_mock,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("eval_run failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"eval failed: {exc}")

    # 顺便与 baseline diff
    baseline = eval_baseline.load_baseline()
    diff = eval_baseline.diff_against_baseline(report, baseline)
    report = report.model_copy(update={
        "baseline_diff": diff.get("deltas", {}),
        "regressions": diff.get("regressions", []),
    })

    return RagEvalRunResponse(report=report)


@router.get(
    "/{project_id}/paper-library/eval/baseline",
)
def eval_get_baseline() -> dict:
    """读当前 baseline.json (含 aggregate metrics + run_id)."""

    return eval_baseline.load_baseline()


@router.post(
    "/{project_id}/paper-library/eval/baseline",
)
def eval_save_baseline(project_id: str) -> dict:
    """跑一次 eval, 把结果存为 baseline (覆盖现有).

    body: 无 (使用默认 fixtures)
    resp: { saved_path, run_id, aggregate_* }
    """

    fixtures_dir = _default_fixtures_dir()
    if not fixtures_dir.exists():
        raise HTTPException(status_code=400, detail=f"fixtures_dir 不存在: {fixtures_dir}")
    try:
        report = rag_eval_pipeline.run_eval(
            project_id=project_id,
            fixtures_dir=fixtures_dir,
            llm_mock=True,
        )
        saved = eval_baseline.save_baseline(report)
    except Exception as exc:  # noqa: BLE001
        logger.warning("eval_save_baseline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"save baseline failed: {exc}")
    return {
        "saved_path": saved,
        "run_id": report.run_id,
        "aggregate_retrieval": report.aggregate_retrieval.model_dump(),
        "aggregate_answer": report.aggregate_answer.model_dump(),
        "aggregate_system": report.aggregate_system.model_dump(),
        "item_count": len(report.items),
    }


def _default_fixtures_dir() -> Path:
    """默认 fixtures 目录 (相对 repo root)."""

    # 默认 tests/fixtures/paper_library_eval (相对于 apps/api 的父目录)
    api_root = Path(__file__).resolve().parent.parent.parent.parent
    return api_root / "tests" / "fixtures" / "paper_library_eval"
