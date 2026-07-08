"""Session 61: 科研检索增强 后端测试 (SOP §7.1).

覆盖:
 0.  M0 P1 修复: retriever.dense_retrieve 签名带 vocab=None (back-compat)
     + S60 本地 RAG ask_local_rag 不会因 vocab 缺失而崩
 1.  research_query_expander: 三维成像损伤题 -> paper/dataset/repo 三类 query
 2.  research_query_expander: paper query 含 3D/damage/imaging/crack
 3.  research_query_expander: dataset query 含 dataset/benchmark/public
 4.  research_query_expander: repo query 含 github/pytorch/implementation 等
 5.  research_query_expander: 空题不抛异常
 6.  source_policy.classify_run_result 区分 query_too_narrow / source_failed
 7.  dataset_enhancer 缺 license -> license_unknown
 8.  dataset_enhancer 缺 url + download -> not_public
 9.  repo_enhancer 缺 license+low star+stale -> 三种 warning 都有
10.  gap_report 区分 source_failed 与 no_* 类缺口
11.  gap_report 生成 next_step_queries
12.  retry_planner: 全 source_failed -> should_retry False
13.  retry_planner: 有 no_dataset + no_repo -> should_retry True + 补搜 query
14.  candidate_actions: paper -> evidence ledger 返回真实 evidence_id
15.  candidate_actions: paper -> paper_library 返回真实 paper_id
16.  candidate_actions: repo 候选 -> paper_library 拒绝
17.  candidate_actions: plan_candidate_retry 返回 3 条 query
18.  orchestrator.run_retrieval 返回 gap_report + retry_round 字段

全部用单测 + monkeypatch, 不依赖真实网络.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest

# ---- M0 修复: dense_retrieve 必须带 vocab 参数, 默认 None 保持 back-compat ----


def test_m0_dense_retrieve_has_vocab_default_none():
    """P1 根因修复验证: dense_retrieve 签名含 vocab: list[str] | None = None.

    ponytail: 一个断言就够了, 旧调用方不传 vocab 仍能工作.
    """
    from app.services.paper_library.retriever import dense_retrieve

    sig = inspect.signature(dense_retrieve)
    assert "vocab" in sig.parameters, f"dense_retrieve 缺 vocab 参数: {sig}"
    # 默认值必须是 None (back-compat)
    assert sig.parameters["vocab"].default is None, (
        f"vocab 默认值应是 None, got {sig.parameters['vocab'].default!r}"
    )


def test_m0_ask_local_rag_smoke_no_corpus():
    """S60 ask_local_rag 不会因 vocab 缺失崩; 空 corpus 返回 no_hit 即可.

    ponytail: 不重跑 session60 整文件, 避免 arxiv 真实网络 + 重复 fixture 开销.
    改用 unit-style 调用: 传不存在的 project_id, 期望 no_hit.
    """

    from app.services.paper_library.local_rag import ask_local_rag

    outcome = ask_local_rag(project_id="s61-m0-empty", question="NEU-DET defect")
    assert outcome.no_hit is True
    assert outcome.retrieval_mode == "no_hit"
    assert outcome.evidence_refs == []


# ---- Fixtures ---- #


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """每个测试用独立 trace 目录, 清空 retrieval + evidence 状态."""

    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path / "traces"))
    from app.services import evidence as ev_store
    from app.services import trace_store as ts
    from app.services.retrieval import (
        candidate_actions,
        orchestrator,
    )

    ev_store.reset_all()
    ts.reset_traces()
    orchestrator.reset_retrieval_state()
    # 清空 candidate_actions 用的内部 _RUNS
    if hasattr(candidate_actions, "_RUNS"):
        candidate_actions._RUNS.clear()
    yield
    ev_store.reset_all()
    ts.reset_traces()
    orchestrator.reset_retrieval_state()
    if hasattr(candidate_actions, "_RUNS"):
        candidate_actions._RUNS.clear()


def _make_paper_candidate(
    candidate_id: str = "cand_paper_1",
    project_id: str = "proj_s61",
) -> "RetrievalCandidate":
    from app.schemas_retrieval import RetrievalCandidate

    return RetrievalCandidate(
        candidate_id=candidate_id,
        project_id=project_id,
        candidate_type="paper",
        source="arxiv",
        title="3D Imaging for Damage Detection",
        abstract="We study 3D imaging techniques for damage detection in civil infrastructure.",
        url="https://arxiv.org/abs/2406.12345",
        year=2024,
        authors=["Alice", "Bob"],
        matched_keywords=["3D", "damage", "detection"],
    )


def _make_repo_candidate(
    candidate_id: str = "cand_repo_1",
    project_id: str = "proj_s61",
) -> "RetrievalCandidate":
    from app.schemas_retrieval import RetrievalCandidate

    return RetrievalCandidate(
        candidate_id=candidate_id,
        project_id=project_id,
        candidate_type="repo",
        source="github",
        title="3d-damage-toolkit",
        url="https://github.com/example/3d-damage-toolkit",
        repo_full_name="example/3d-damage-toolkit",
        stars=42,
        license="MIT",
        updated_at="2025-01-15T00:00:00Z",
        matched_keywords=["3D", "damage"],
    )


def _seed_run_with_candidate(project_id: str, *candidates: "RetrievalCandidate") -> str:
    """把候选注入 orchestrator._RUNS, 返回 run_id."""

    from app.services.retrieval import orchestrator
    from app.schemas_retrieval import (
        QueryPlan,
        QueryPlanLayer,
        RetrievalRun,
        SourceResult,
    )

    plan = QueryPlan(
        project_id=project_id,
        raw_topic="seed topic",
        paper_queries=[QueryPlanLayer(layer="L1", queries=["seed"])],
        dataset_queries=[QueryPlanLayer(layer="L1", queries=["seed"])],
        repo_queries=[QueryPlanLayer(layer="L1", queries=["seed"])],
    )
    run_id = "ret_s61_seed"
    run = RetrievalRun(
        run_id=run_id,
        project_id=project_id,
        query_plan=plan,
        sources=["arxiv", "github"],
        source_results=[
            SourceResult(source="arxiv", status="completed", candidate_count=1),
        ],
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        status="completed",
        total_candidates=len(candidates),
        candidates=list(candidates),
    )
    with orchestrator._LOCK:
        orchestrator._RUNS[project_id] = [run]
    return run_id


# ---- 1-5: research_query_expander ---- #


def test_research_query_expander_three_d_damage():
    """三维成像损伤题 -> paper/dataset/repo 三类 query 都有."""

    from app.services.retrieval.research_query_expander import expand_topic

    r = expand_topic("基于三维成像的损伤智能检测")
    assert r.paper_queries, "paper_queries 应非空"
    assert r.dataset_queries, "dataset_queries 应非空"
    assert r.repo_queries, "repo_queries 应非空"
    en_paper = " ".join(r.paper_queries).lower()
    assert any(tok in en_paper for tok in ("3d", "damage", "imaging", "crack")), (
        f"paper query 应含 3D/damage/imaging/crack, got: {r.paper_queries}"
    )


def test_research_query_expander_dataset_contains_keyword():
    """dataset query 必须含 dataset/benchmark/public/kaggle/huggingface."""

    from app.services.retrieval.research_query_expander import expand_topic

    r = expand_topic("基于三维成像的损伤智能检测")
    blob = " ".join(r.dataset_queries).lower()
    assert any(tok in blob for tok in ("dataset", "benchmark", "public", "kaggle", "huggingface")), (
        f"dataset query 缺必备 token: {r.dataset_queries}"
    )


def test_research_query_expander_repo_contains_keyword():
    """repo query 必须含 github/pytorch/implementation/baseline/code/train."""

    from app.services.retrieval.research_query_expander import expand_topic

    r = expand_topic("基于三维成像的损伤智能检测")
    blob = " ".join(r.repo_queries).lower()
    assert any(
        tok in blob for tok in ("github", "pytorch", "implementation", "baseline", "code", "train")
    ), f"repo query 缺必备 token: {r.repo_queries}"


def test_research_query_expander_empty_topic():
    """空题目不抛异常, 返回空 queries."""

    from app.services.retrieval.research_query_expander import expand_topic

    r = expand_topic("")
    assert r.paper_queries == []
    assert r.dataset_queries == []
    assert r.repo_queries == []


# ---- 6: source_policy ---- #


def test_source_policy_classify_run_result():
    """空 source_results -> query_too_narrow; 全 failed -> source_failed."""

    from app.schemas_retrieval import SourceResult
    from app.services.retrieval.source_policy import classify_run_result

    # 空 results + 0 候选 -> query_too_narrow
    reason_empty = classify_run_result([], "paper", candidate_count=0)
    assert reason_empty == "query_too_narrow", reason_empty

    # 全 failed + 0 候选 -> source_failed
    failed = [
        SourceResult(source="openalex", status="failed", candidate_count=0, error="net"),
        SourceResult(source="arxiv", status="failed", candidate_count=0, error="net"),
    ]
    reason_failed = classify_run_result(failed, "paper", candidate_count=0)
    assert reason_failed == "source_failed", reason_failed


# ---- 7-8: dataset_enhancer ---- #


def test_dataset_enhancer_emits_license_unknown():
    """license=None -> warnings 含 license_unknown."""

    from app.schemas_retrieval import RetrievalCandidate
    from app.services.retrieval.dataset_enhancer import enhance_dataset

    cand = RetrievalCandidate(
        candidate_id="d1",
        project_id="p1",
        candidate_type="dataset",
        source="huggingface",
        title="Some Dataset",
        url="https://huggingface.co/datasets/x",
        matched_keywords=["damage"],
    )
    r = enhance_dataset(cand)
    assert "license_unknown" in r.warnings, r.warnings


def test_dataset_enhancer_emits_not_public():
    """无 url 且 raw 无 download -> warnings 含 not_public."""

    from app.schemas_retrieval import RetrievalCandidate
    from app.services.retrieval.dataset_enhancer import enhance_dataset

    cand = RetrievalCandidate(
        candidate_id="d2",
        project_id="p1",
        candidate_type="dataset",
        source="huggingface",
        title="Closed Dataset",
        url=None,
        license="MIT",
        matched_keywords=["damage"],
        raw={},  # 无 download / download_url
    )
    r = enhance_dataset(cand)
    assert "not_public" in r.warnings, r.warnings
    # license 有, 不应同时报 license_unknown
    assert "license_unknown" not in r.warnings, r.warnings


# ---- 9: repo_enhancer ---- #


def test_repo_enhancer_emits_stale_no_license_low_star():
    """stars=2, 无 license, 3 年前更新 -> 三种 warning 都有."""

    from app.schemas_retrieval import RetrievalCandidate
    from app.services.retrieval.repo_enhancer import enhance_repo

    old = (datetime.now(timezone.utc) - timedelta(days=365 * 3)).isoformat()
    cand = RetrievalCandidate(
        candidate_id="r1",
        project_id="p1",
        candidate_type="repo",
        source="github",
        title="stale repo",
        url="https://github.com/a/b",
        repo_full_name="a/b",
        stars=2,
        license=None,
        updated_at=old,
    )
    r = enhance_repo(cand)
    for w in ("no_license", "low_star", "stale_repo"):
        assert w in r.warnings, f"missing {w} in {r.warnings}"


# ---- 10-11: gap_report ---- #


def test_gap_report_distinguishes_source_failed():
    """2 failed + (0,0,0) -> gaps 含 source_failed + no_paper/dataset/repo.

    summary 必须提到 '失败' (而非仅仅 '未找到').
    """

    from app.schemas_retrieval import SourceResult
    from app.services.retrieval.gap_report import build_gap_report

    failed = [
        SourceResult(source="openalex", status="failed", candidate_count=0, error="net"),
        SourceResult(source="arxiv", status="failed", candidate_count=0, error="net"),
    ]
    g = build_gap_report(0, 0, 0, failed)
    cats = [gi.category for gi in g.gaps]
    for required in ("source_failed", "no_paper", "no_dataset", "no_repo"):
        assert required in cats, f"missing {required} in {cats}"
    assert "失败" in g.summary_text, f"summary 应提 '失败': {g.summary_text}"


def test_gap_report_emits_next_step_queries():
    """同输入 -> next_step_queries 非空."""

    from app.schemas_retrieval import SourceResult
    from app.services.retrieval.gap_report import build_gap_report

    failed = [
        SourceResult(source="openalex", status="failed", candidate_count=0, error="net"),
        SourceResult(source="huggingface", status="failed", candidate_count=0, error="net"),
    ]
    g = build_gap_report(0, 0, 0, failed)
    assert g.next_step_queries, "next_step_queries 应非空"
    assert len(g.next_step_queries) >= 1


# ---- 12-13: retry_planner ---- #


def test_retry_planner_skips_source_failed():
    """gap 仅有 source_failed -> should_retry False."""

    from app.services.retrieval.gap_report import GapItem, GapReport
    from app.services.retrieval.retry_planner import plan_retry

    g = GapReport(
        gaps=[GapItem(category="source_failed", details="all failed")],
    )
    p = plan_retry(g, "topic")
    assert p.should_retry is False, p
    assert p.extra_queries_by_type == {}, p


def test_retry_planner_emits_extra_queries_for_dataset_repo():
    """gap 含 no_dataset + no_repo -> should_retry True + dataset/repo 补搜非空."""

    from app.services.retrieval.gap_report import GapItem, GapReport
    from app.services.retrieval.retry_planner import plan_retry

    g = GapReport(
        gaps=[
            GapItem(category="no_dataset", details="x"),
            GapItem(category="no_repo", details="y"),
        ],
    )
    p = plan_retry(g, "三维成像损伤检测")
    assert p.should_retry is True, p
    assert p.extra_queries_by_type.get("dataset"), p.extra_queries_by_type
    assert p.extra_queries_by_type.get("repo"), p.extra_queries_by_type
    # query 必须含 raw_topic 替换 {topic}
    assert all("三维成像损伤检测" in q for q in p.extra_queries_by_type["dataset"])
    assert all("三维成像损伤检测" in q for q in p.extra_queries_by_type["repo"])


# ---- 14-17: candidate_actions ---- #


def test_candidate_actions_paper_to_evidence():
    """paper 候选加入 evidence ledger -> 返回真实 evidence_id (man_paper_ 前缀)."""

    from app.services.retrieval import candidate_actions

    pid = "proj_s61_ce_1"
    cand = _make_paper_candidate(candidate_id="cand_p_1", project_id=pid)
    _seed_run_with_candidate(pid, cand)

    r = candidate_actions.add_candidate_to_evidence(pid, "cand_p_1")
    assert r.get("ok") is True, r
    assert r.get("evidence_id", "").startswith("man_paper_"), r
    assert r.get("candidate_id") == "cand_p_1"


def test_candidate_actions_paper_to_library_returns_paper_id():
    """paper 候选加入 paper library -> 返回 paper_id (paper_mn_ 前缀)."""

    from app.services.retrieval import candidate_actions

    pid = "proj_s61_ce_2"
    cand = _make_paper_candidate(candidate_id="cand_p_2", project_id=pid)
    _seed_run_with_candidate(pid, cand)

    r = candidate_actions.add_candidate_to_paper_library(pid, "cand_p_2")
    assert r.get("ok") is True, r
    assert r.get("paper_id", "").startswith("paper_mn_"), r
    assert r.get("candidate_id") == "cand_p_2"


def test_candidate_actions_rejects_non_paper_to_library():
    """repo 候选加入 paper library -> ok=False, message 提示仅 paper 可入."""

    from app.services.retrieval import candidate_actions

    pid = "proj_s61_ce_3"
    cand = _make_repo_candidate(candidate_id="cand_r_1", project_id=pid)
    _seed_run_with_candidate(pid, cand)

    r = candidate_actions.add_candidate_to_paper_library(pid, "cand_r_1")
    assert r.get("ok") is False, r
    assert "paper" in r.get("message", "").lower(), r
    assert r.get("paper_id") == ""


def test_candidate_actions_plan_retry_returns_queries():
    """plan_candidate_retry 返回 3 条衍生 query, ok=True."""

    from app.services.retrieval import candidate_actions

    pid = "proj_s61_ce_4"
    cand = _make_paper_candidate(candidate_id="cand_p_4", project_id=pid)
    _seed_run_with_candidate(pid, cand)

    r = candidate_actions.plan_candidate_retry(pid, "cand_p_4")
    assert r.get("ok") is True, r
    assert isinstance(r.get("queries"), list), r
    assert len(r["queries"]) == 3, r
    # query 应基于 title
    title_part = cand.title.split()[0]  # "3D"
    assert all(title_part in q or cand.title[:10] in q for q in r["queries"]), r["queries"]


# ---- 18: orchestrator 集成 ---- #


def test_orchestrator_integration_returns_gap_report():
    """run_retrieval 返回 RetrievalRun, 含 gap_report (非 None) + retry_round in (0, 1)."""

    from app.schemas_retrieval import RetrievalSearchRequest
    from app.services.retrieval.orchestrator import run_retrieval

    req = RetrievalSearchRequest(
        scope=["paper", "dataset", "repo"],
        sources=["openalex", "arxiv", "github", "huggingface"],
        top_k_per_source=2,
    )

    async def _go():
        return await run_retrieval(
            "proj_s61_orch", "基于三维成像的损伤智能检测", req, client=None,
        )

    run = asyncio.run(_go())
    assert run.gap_report is not None, run
    assert run.retry_round in (0, 1), run.retry_round
    # gap_report 必须含 summary / gaps / next_step_queries / counts
    gr = run.gap_report
    assert "summary" in gr, gr
    assert "gaps" in gr, gr
    assert "next_step_queries" in gr, gr
    assert "counts" in gr, gr
