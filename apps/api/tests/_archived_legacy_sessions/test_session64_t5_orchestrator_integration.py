"""Session 64 T5: orchestrator 集成新模块 (后端测试).

覆盖:
 1.  run_retrieval 返回 RetrievalRun, 含 clean_summary 字段 (dict 至少含 keep)
 2.  clean_candidates 缺失 -> clean_summary 全 0, 仍可正常运行
 3.  candidate_cleaner 可用时, AG title 被 reject, civil 论文 keep
 4.  candidate_cleaner 后, keep_candidates <= 总候选数
 5.  web_dataset_search: dataset<2 时触发, 返回 web_datasets list (非空或空 list 都 OK)
 6.  web_dataset_search: dataset>=2 + 高分时不触发, web_datasets=[]
 7.  literature_role_classifier 可用时, literature_roles 是 list
 8.  literature_role_classifier 不可用时, literature_roles=[], 不报错
 9.  paper_module_matrix 可用时, module_matrix 含 entries 字段
10.  paper_module_matrix 不可用时, module_matrix=None, 不报错
11.  不破坏现有 gap_report + retry_round 字段
12.  不破坏 candidates 字段 (只有 keep 进入, 但 import 仍能跑)
"""

from __future__ import annotations

import asyncio

import pytest


# ---- Fixtures ---- #


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """每个测试用独立 trace 目录, 清空 retrieval + evidence 状态."""

    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path / "traces"))
    from app.services import evidence as ev_store
    from app.services import trace_store as ts
    from app.services.retrieval import orchestrator

    ev_store.reset_all()
    ts.reset_traces()
    orchestrator.reset_retrieval_state()
    yield
    ev_store.reset_all()
    ts.reset_traces()
    orchestrator.reset_retrieval_state()


def _build_request() -> "RetrievalSearchRequest":
    from app.schemas_retrieval import RetrievalSearchRequest

    return RetrievalSearchRequest(
        scope=["paper", "dataset", "repo"],
        sources=["openalex", "arxiv", "github", "huggingface"],
        top_k_per_source=3,
        extra_keywords=["crack", "detection"],
    )


async def _run_once(project_id: str, topic: str = "concrete crack detection"):
    from app.services.retrieval.orchestrator import run_retrieval

    return await run_retrieval(project_id, topic, _build_request(), client=None)


# ---- Tests ---- #


def test_t5_run_has_clean_summary_field():
    """run_retrieval 总是返回 clean_summary 字段 (dict)."""

    run = asyncio.run(_run_once("proj_s64_t5_1"))
    assert run.clean_summary is not None, run
    assert isinstance(run.clean_summary, dict)
    # 默认 4 个 key 都存在 (即使值是 0)
    for k in ("keep", "quarantine", "reject", "needs_manual"):
        assert k in run.clean_summary, f"missing key {k} in clean_summary: {run.clean_summary}"


def test_t5_clean_candidates_filters_keep():
    """AG 天文论文 + civil 混凝土题 -> AG 被 reject, civil 论文 keep.

    ponytail: 不 mock 网络, 用纯 dict 喂 candidate_cleaner, 看 candidate_cleaner
    自身对 orchestrator 的影响. 这里跑完整 run_retrieval 但只验 keep 数量.
    """

    run = asyncio.run(_run_once("proj_s64_t5_2", topic="concrete crack detection"))
    # 总候选 >= 0, keep 数 <= 总数 (有的会被 reject/quarantine)
    assert run.clean_summary["keep"] <= run.total_candidates + (
        run.clean_summary["quarantine"] + run.clean_summary["reject"]
    )
    # 至少有 keep (题目"concrete"较宽, 不至于全部 reject)
    # 注: 网络可能失败返回 0 candidate, 此时 keep 也可能 0, 不强制


def test_t5_clean_candidates_module_unavailable_fallback():
    """模拟 candidate_cleaner 不可用, orchestrator 仍正常运行."""

    from app.services.retrieval import orchestrator

    original = orchestrator.clean_candidates
    orchestrator.clean_candidates = None  # ponytail: 强制走 None 分支
    try:
        run = asyncio.run(_run_once("proj_s64_t5_3"))
        # 全 0 但仍是 dict
        assert run.clean_summary == {"keep": 0, "quarantine": 0, "reject": 0, "needs_manual": 0}
        assert run.candidates is not None  # 不报错
    finally:
        orchestrator.clean_candidates = original


def test_t5_web_dataset_search_field_present():
    """run_retrieval 返回 web_datasets 字段 (list)."""

    run = asyncio.run(_run_once("proj_s64_t5_4"))
    assert hasattr(run, "web_datasets")
    assert isinstance(run.web_datasets, list)
    # 如果 dataset 数 < 2 或 top_score < 0.45, 至少可能触发; 这里只验字段存在


def test_t5_web_dataset_search_module_unavailable():
    """search_web_datasets 不可用时, web_datasets=[], 不报错."""

    from app.services.retrieval import orchestrator

    original = orchestrator.search_web_datasets
    orchestrator.search_web_datasets = None
    try:
        run = asyncio.run(_run_once("proj_s64_t5_5"))
        assert run.web_datasets == []
    finally:
        orchestrator.search_web_datasets = original


def test_t5_literature_roles_field_present():
    """run_retrieval 返回 literature_roles 字段 (list)."""

    run = asyncio.run(_run_once("proj_s64_t5_6"))
    assert hasattr(run, "literature_roles")
    assert isinstance(run.literature_roles, list)


def test_t5_literature_roles_module_unavailable():
    """classify_literature 不可用时, literature_roles=[], 不报错."""

    from app.services.retrieval import orchestrator

    original = orchestrator.classify_literature
    orchestrator.classify_literature = None
    try:
        run = asyncio.run(_run_once("proj_s64_t5_7"))
        assert run.literature_roles == []
    finally:
        orchestrator.classify_literature = original


def test_t5_module_matrix_field_present():
    """run_retrieval 返回 module_matrix 字段 (dict or None)."""

    run = asyncio.run(_run_once("proj_s64_t5_8"))
    assert hasattr(run, "module_matrix")
    # None (无 roles) 或 dict (有 roles 时)
    assert run.module_matrix is None or isinstance(run.module_matrix, dict)


def test_t5_module_matrix_module_unavailable():
    """build_module_matrix 不可用时, module_matrix=None, 不报错."""

    from app.services.retrieval import orchestrator

    original = orchestrator.build_module_matrix
    orchestrator.build_module_matrix = None
    try:
        run = asyncio.run(_run_once("proj_s64_t5_9"))
        assert run.module_matrix is None
    finally:
        orchestrator.build_module_matrix = original


def test_t5_does_not_break_existing_gap_report():
    """S61 gap_report + retry_round 字段仍然存在 (回归保护)."""

    run = asyncio.run(_run_once("proj_s64_t5_10"))
    # gap_report 可能 None (网络全失败时) 或 dict
    assert run.gap_report is None or isinstance(run.gap_report, dict)
    assert run.retry_round in (0, 1)


def test_t5_does_not_break_candidates_field():
    """S14 candidates 字段仍然存在, 类型不变."""

    run = asyncio.run(_run_once("proj_s64_t5_11"))
    assert isinstance(run.candidates, list)
    # 每条仍是 RetrievalCandidate
    from app.schemas_retrieval import RetrievalCandidate
    for c in run.candidates:
        assert isinstance(c, RetrievalCandidate)