"""多源检索协调器 (SOP §4 / §8 / §12 / §13).

负责:
1. 生成 QueryPlan
2. 并发跑各 source adapter
3. 归一化候选
4. 跨候选去重
5. 与 Evidence Ledger 去重
6. 评分
7. 持久化最近一次 run
8. import -> Evidence Ledger
9. 写 trace 事件
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any

from ...schemas_retrieval import (
    CandidateType,
    QueryPlan,
    RetrievalCandidate,
    RetrievalImportRequest,
    RetrievalImportResponse,
    RetrievalRun,
    RetrievalSearchRequest,
    RetrievalStatus,
    RetrievalSummaryResponse,
    SearchSource,
    SourceResult,
)
from ..trace_store import append_trace
from .adapters import REGISTRY
from .dedup import dedup_candidates, is_duplicate_in_ledger
from .normalizer import normalize_candidate
from .query_plan import build_query_plan
from .ranker import score_dataset, score_paper, score_repo


# ---------- 状态 ---------- #

_LOCK = threading.RLock()
_RUNS: dict[str, list[RetrievalRun]] = {}


def _runs(project_id: str) -> list[RetrievalRun]:
    with _LOCK:
        return list(_RUNS.get(project_id, []))


def _add_run(run: RetrievalRun) -> None:
    with _LOCK:
        _RUNS.setdefault(run.project_id, []).append(run)


# ---------- Source 类型 -> evidence_type / skill 映射 ---------- #

_SOURCE_TO_CANDIDATE_TYPE: dict[SearchSource, CandidateType] = {
    "openalex": "paper",
    "semantic_scholar": "paper",
    "arxiv": "paper",
    "github": "repo",
    "huggingface": "dataset",
    "kaggle": "dataset",
    "manual_fallback": "note",
}

_TYPE_TO_SKILL: dict[CandidateType, str] = {
    "paper": "paper-card",
    "dataset": "dataset-validation",
    "repo": "github-baseline",
    "project_page": "paper-card",
    "note": "paper-card",
}


# ---------- 检索运行 ---------- #


async def run_retrieval(
    project_id: str,
    raw_topic: str,
    request: RetrievalSearchRequest,
    *,
    client: Any | None = None,
) -> RetrievalRun:
    """按 SOP §13.1 执行一次检索."""

    # 1) 查询计划
    plan = build_query_plan(
        project_id=project_id,
        raw_topic=raw_topic,
        extra_keywords=request.extra_keywords,
    )

    run_id = f"ret_{uuid.uuid4().hex[:10]}"
    started_at = _now_iso()

    # trace: retrieval_run_started
    append_trace(
        project_id,
        action="retrieval_run_started",
        target_type="retrieval_run",
        target_id=run_id,
        actor="user",
        after={
            "sources": list(request.sources),
            "scope": list(request.scope),
            "top_k_per_source": request.top_k_per_source,
        },
        reason=raw_topic or "(empty topic)",
    )

    # 2) 准备每个 source 的 query 列表
    def _queries_for(source: SearchSource) -> list[str]:
        ctype = _SOURCE_TO_CANDIDATE_TYPE[source]
        if ctype == "paper":
            layers = plan.paper_queries
        elif ctype == "dataset":
            layers = plan.dataset_queries
        elif ctype == "repo":
            layers = plan.repo_queries
        else:
            layers = []
        out: list[str] = []
        for layer in layers:
            out.extend(layer.queries)
        return out

    # 3) 并发跑 source
    scope_set: set[CandidateType] = set(request.scope)

    async def _run_one(source: SearchSource) -> dict:
        ctype = _SOURCE_TO_CANDIDATE_TYPE[source]
        if scope_set and ctype not in scope_set and ctype != "note":
            return {"source": source, "status": "completed", "candidate_count": 0, "error": None, "duration_ms": 0, "_raws": []}
        queries = _queries_for(source)
        if not queries:
            return {"source": source, "status": "completed", "candidate_count": 0, "error": None, "duration_ms": 0, "_raws": []}
        runner = REGISTRY.get(source)
        if runner is None:
            return {"source": source, "status": "failed", "candidate_count": 0, "error": "no adapter", "duration_ms": 0, "_raws": []}
        import time as _t

        t0 = _t.time()
        try:
            raws = await runner(queries, request.top_k_per_source, client=client)
        except Exception as e:  # noqa: BLE001
            duration = int((_t.time() - t0) * 1000)
            append_trace(
                project_id,
                action="retrieval_source_failed",
                target_type="source",
                target_id=source,
                actor="system",
                reason=f"{type(e).__name__}: {e}",
            )
            return {"source": source, "status": "failed", "candidate_count": 0, "error": f"{type(e).__name__}: {e}", "duration_ms": duration, "_raws": []}
        duration = int((_t.time() - t0) * 1000)
        return {
            "source": source, "status": "completed", "candidate_count": len(raws),
            "error": None, "duration_ms": duration, "_raws": list(raws or []),
        }

    tasks = [_run_one(s) for s in request.sources]
    source_results_raw = await asyncio.gather(*tasks) if tasks else []

    # 4) 收集 + 归一化候选
    candidates: list[RetrievalCandidate] = []
    source_results: list[SourceResult] = []
    for r in source_results_raw:
        raws = r.pop("_raws", None) or []
        raws_clean = [x for x in raws if isinstance(x, dict)]
        for raw in raws_clean:
            cid = f"cand_{uuid.uuid4().hex[:10]}"
            cand = normalize_candidate(
                raw,
                project_id=project_id,
                source=r["source"],
                candidate_id=cid,
            )
            # 收集 matched_keywords
            for kw in request.extra_keywords or []:
                if kw and (kw.lower() in (cand.title or "").lower() or kw.lower() in (cand.abstract or "").lower()):
                    if kw not in cand.matched_keywords:
                        cand.matched_keywords.append(kw)
            candidates.append(cand)
        sr = SourceResult(
            source=r["source"], status=r["status"], candidate_count=r["candidate_count"],
            error=r["error"], duration_ms=r["duration_ms"],
        )
        source_results.append(sr)

    # 5) 评分
    for cand in candidates:
        if cand.candidate_type == "paper":
            cand.retrieval_score = score_paper(cand, query_keywords=request.extra_keywords)
        elif cand.candidate_type == "dataset":
            cand.retrieval_score = score_dataset(cand, query_keywords=request.extra_keywords)
        elif cand.candidate_type == "repo":
            cand.retrieval_score = score_repo(cand, query_keywords=request.extra_keywords)
        else:
            cand.retrieval_score = 0.3

    # 6) 去重
    deduped = dedup_candidates(candidates)

    # 7) 与 Evidence Ledger 去重
    ledger_items: list = []
    try:
        from .. import evidence as _ev

        ledger = _ev.get_ledger(project_id)
        ledger_items = [*ledger.papers, *ledger.datasets, *ledger.repos, *ledger.notes]
    except Exception:
        ledger_items = []
    for cand in deduped:
        if is_duplicate_in_ledger(cand, ledger_items):
            cand.already_in_ledger = True

    # 8) 排序: non-duplicate 在前
    deduped.sort(
        key=lambda c: (
            c.is_duplicate,
            c.already_in_ledger,
            -c.retrieval_score,
        )
    )

    finished_at = _now_iso()
    overall_status: RetrievalStatus = "completed"
    if any(r.status == "failed" for r in source_results):
        overall_status = "partial" if deduped else "failed"
    if all(r.status == "failed" for r in source_results) and request.sources:
        overall_status = "failed"

    run = RetrievalRun(
        run_id=run_id,
        project_id=project_id,
        query_plan=plan,
        sources=list(request.sources),
        source_results=source_results,
        started_at=started_at,
        finished_at=finished_at,
        status=overall_status,
        total_candidates=len(deduped),
        imported_count=0,
        errors=[r.error for r in source_results if r.error],
        candidates=deduped,
    )
    _add_run(run)

    # trace: retrieval_run_completed
    append_trace(
        project_id,
        action="retrieval_run_completed",
        target_type="retrieval_run",
        target_id=run_id,
        actor="system",
        after={
            "status": overall_status,
            "total_candidates": len(deduped),
            "duplicates": sum(1 for c in deduped if c.is_duplicate),
            "errors": run.errors,
        },
    )

    return run


# ---------- 读取 ---------- #


def get_last_run(project_id: str) -> RetrievalRun | None:
    runs = _runs(project_id)
    return runs[-1] if runs else None


def get_run_by_id(project_id: str, run_id: str) -> RetrievalRun | None:
    for r in _runs(project_id):
        if r.run_id == run_id:
            return r
    return None


def list_runs(project_id: str) -> list[RetrievalRun]:
    return _runs(project_id)


def get_summary(project_id: str) -> RetrievalSummaryResponse:
    runs = _runs(project_id)
    if not runs:
        return RetrievalSummaryResponse(project_id=project_id)
    last = runs[-1]
    paper_n = sum(1 for c in last.candidates if c.candidate_type == "paper" and not c.is_duplicate)
    ds_n = sum(1 for c in last.candidates if c.candidate_type == "dataset" and not c.is_duplicate)
    repo_n = sum(1 for c in last.candidates if c.candidate_type == "repo" and not c.is_duplicate)
    dup_n = sum(1 for c in last.candidates if c.is_duplicate)
    success = {r.source: 1 for r in last.source_results if r.status == "completed"}
    failure = {r.source: 1 for r in last.source_results if r.status == "failed"}
    return RetrievalSummaryResponse(
        project_id=project_id,
        last_run_id=last.run_id,
        last_run_at=last.finished_at or last.started_at,
        source_success=success,
        source_failure=failure,
        paper_candidates=paper_n,
        dataset_candidates=ds_n,
        repo_candidates=repo_n,
        duplicate_candidates=dup_n,
        imported_candidates=last.imported_count,
        last_errors=list(last.errors),
        total_runs=len(runs),
    )


# ---------- 导入 ---------- #


def import_candidates(
    project_id: str,
    request: RetrievalImportRequest,
) -> RetrievalImportResponse:
    """把 run 的选中候选导入 Evidence Ledger."""

    run = get_run_by_id(project_id, request.run_id)
    if run is None:
        return RetrievalImportResponse(
            run_id=request.run_id,
            imported=0, skipped_duplicates=0, skipped_rejected=0,
            evidence_ids=[], skipped_evidence_ids=[],
            message="run 不存在",
        )

    selected: list[RetrievalCandidate] = []
    if request.candidate_ids:
        cand_by_id = {c.candidate_id: c for c in run.candidates}
        for cid in request.candidate_ids:
            c = cand_by_id.get(cid)
            if c is not None:
                selected.append(c)
    else:
        # 默认导 all non-duplicate non-already-in
        selected = [
            c for c in run.candidates
            if not c.is_duplicate and not c.already_in_ledger
        ]

    if not selected:
        return RetrievalImportResponse(
            run_id=request.run_id,
            imported=0, skipped_duplicates=0, skipped_rejected=0,
            evidence_ids=[], skipped_evidence_ids=[],
            message="没有可导入的候选",
        )

    from .. import evidence as _ev

    imported_ids: list[str] = []
    skipped_ids: list[str] = []
    skill_for_type = _TYPE_TO_SKILL

    for cand in selected:
        # 已存在 ledger 中 -> skip
        if cand.already_in_ledger:
            skipped_ids.append(cand.candidate_id)
            append_trace(
                project_id,
                action="retrieval_candidate_skipped_duplicate",
                target_type="candidate",
                target_id=cand.candidate_id,
                actor="system",
                reason="已存在于 Evidence Ledger",
            )
            continue
        # 自身 duplicate -> skip
        if cand.is_duplicate and cand.duplicate_of:
            skipped_ids.append(cand.candidate_id)
            append_trace(
                project_id,
                action="retrieval_candidate_skipped_duplicate",
                target_type="candidate",
                target_id=cand.candidate_id,
                actor="system",
                reason=f"duplicate of {cand.duplicate_of}",
            )
            continue

        # 构造对应 evidence 输入
        eid = _build_evidence_from_candidate(project_id, cand, request.workspace_lane)
        if eid is None:
            skipped_ids.append(cand.candidate_id)
            continue
        imported_ids.append(eid)  # 用真实 evidence_id
        append_trace(
            project_id,
            action="retrieval_candidate_imported",
            target_type="evidence",
            target_id=eid,
            evidence_id=eid,
            actor="user",
            before={"candidate_id": cand.candidate_id},
            after={
                "candidate_type": cand.candidate_type,
                "source": cand.source,
                "review_status": "pending",
                "workspace_lane": request.workspace_lane,
                "created_by_skill": skill_for_type.get(cand.candidate_type, "paper-card"),
            },
            source=cand.source,
        )

    # 更新 run.imported_count
    with _LOCK:
        for r in _RUNS.get(project_id, []):
            if r.run_id == request.run_id:
                r.imported_count = len(imported_ids)
                break

    # 可选触发 verification
    verified_count = 0
    if request.auto_verify and imported_ids:
        try:
            from .. import verification as _ver

            for eid in imported_ids:
                item = _ev.get_item(eid)
                if item is None:
                    continue
                result = _ver.verify_evidence_item(item)
                updated = _ver.apply_verification(item, result)
                try:
                    _ev.update_verification_field(eid, updated)
                    verified_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    msg = f"已导入 {len(imported_ids)} 条候选"
    if verified_count:
        msg += f", 自动验证 {verified_count} 条"

    return RetrievalImportResponse(
        run_id=request.run_id,
        imported=len(imported_ids),
        skipped_duplicates=len(skipped_ids),
        skipped_rejected=0,
        evidence_ids=imported_ids,
        skipped_evidence_ids=skipped_ids,
        message=msg,
    )


def _build_evidence_from_candidate(
    project_id: str,
    cand: RetrievalCandidate,
    workspace_lane: str,
) -> str | None:
    """把候选写入 Evidence Ledger (通过 evidence.add_*_manual)."""

    from .. import evidence as _ev
    from ...schemas_evidence import (
        DatasetManualCreate,
        PaperManualCreate,
        RepoManualCreate,
    )

    try:
        if cand.candidate_type == "paper":
            body = PaperManualCreate(
                title=cand.title,
                authors=list(cand.authors or []),
                year=cand.year,
                url=cand.url,
                doi=cand.doi,
                arxiv_id=cand.arxiv_id,
                abstract=cand.abstract,
                tags=[cand.source],
                review_status="pending",
            )
            resp = _ev.add_paper_manual(project_id, body)
            if not resp.ok:
                return None
            # 改 lane + source_mode + skill
            _post_import_patch(resp.evidence_id, source_mode="auto_search", workspace_lane=workspace_lane)
            return resp.evidence_id

        if cand.candidate_type == "dataset":
            body = DatasetManualCreate(
                name=cand.title,
                scale=None,
                license=cand.license,
                download=cand.url,
                modality=[],
                annotation=None,
                review_status="pending",
            )
            resp = _ev.add_dataset_manual(project_id, body)
            if not resp.ok:
                return None
            _post_import_patch(resp.evidence_id, source_mode="auto_search", workspace_lane=workspace_lane)
            return resp.evidence_id

        if cand.candidate_type == "repo":
            body = RepoManualCreate(
                name=cand.repo_full_name or cand.title,
                repository_url=cand.url,
                paper_title=None,
                license=cand.license,
                has_readme=bool((cand.raw or {}).get("description")),
                has_env_file=False,
                has_training_script=False,
                has_eval_script=False,
                review_status="pending",
            )
            resp = _ev.add_repo_manual(project_id, body)
            if not resp.ok:
                return None
            _post_import_patch(resp.evidence_id, source_mode="auto_search", workspace_lane=workspace_lane)
            return resp.evidence_id

        # project_page / note 走 note 通道: 通过 add_note_manual 不存在, 退化为 paper 通道
        body = PaperManualCreate(
            title=cand.title,
            url=cand.url,
            year=cand.year,
            abstract=cand.abstract,
            tags=[cand.source, cand.candidate_type],
            review_status="pending",
        )
        resp = _ev.add_paper_manual(project_id, body)
        if not resp.ok:
            return None
        _post_import_patch(resp.evidence_id, source_mode="auto_search", workspace_lane=workspace_lane)
        return resp.evidence_id
    except Exception:
        return None


def _post_import_patch(evidence_id: str, *, source_mode: str, workspace_lane: str) -> None:
    """import 后修改 source_mode / workspace_lane / created_by_skill."""

    from .. import evidence as _ev
    from ...schemas_evidence import EvidenceItem

    item = _ev.get_item(evidence_id)
    if item is None:
        return
    new_data = item.model_dump()
    new_data["source_mode"] = source_mode
    new_data["workspace_lane"] = workspace_lane
    # created_by_skill 来自 candidate_type
    skill = _TYPE_TO_SKILL.get(item.evidence_type, "paper-card")
    new_data["created_by_skill"] = skill
    new_data["verification_status"] = "unverified"
    new_data["verification_source"] = "none"
    new_data["verification_confidence"] = None
    new_data["verification_checked_at"] = None
    new_data["verification_warnings"] = []
    new_data["verification_metadata"] = {}
    new_data["url_verified"] = False
    try:
        _ev._LEDGER  # noqa: SLF001
    except AttributeError:
        pass
    # 直接通过 _LEDGER 写回
    from .. import evidence as _ev2
    with _ev2._LEDGER_LOCK:  # type: ignore[attr-defined]
        for proj in _ev2._LEDGER.values():  # type: ignore[attr-defined]
            if evidence_id in proj.items:
                proj.items[evidence_id] = EvidenceItem(**new_data)
                return


# ---------- 测试用 ---------- #


def reset_retrieval_state() -> None:
    """清空所有 runs (测试用)."""

    global _RUNS
    with _LOCK:
        _RUNS = {}


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat()