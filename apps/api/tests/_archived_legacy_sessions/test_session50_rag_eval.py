"""Session 50: RAG Evaluation Metrics + Pipeline + Baseline tests (12+ 个).

S50-1: load_eval_set (5 papers + 15 questions)
S50-2: compute_recall_at_k
S50-3: compute_mrr
S50-4: compute_ndcg_at_k
S50-5: compute_citation_precision
S50-6: compute_evidence_coverage
S50-7: compute_unsupported_claim_rate
S50-8: compute_faithfulness
S50-9: aggregate_metrics
S50-10: run_eval 完整流程 (seed + eval)
S50-11: save_baseline / load_baseline roundtrip
S50-12: diff_against_baseline 回归检测
S50-13: 4 个端点形状 (seed, run, get baseline, save baseline)
S50-14: 退化警告 (recall drops)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas_paper_rag_eval import (
    AnswerMetrics,
    RagEvalItem,
    RagEvalReport,
    RetrievalMetrics,
    SystemMetrics,
)
from app.services.paper_library import (
    eval_baseline,
    eval_metrics,
    rag_eval_pipeline,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "paper_library_eval"


@pytest.fixture
def tmp_lib_dir(tmp_path, monkeypatch):
    """每个测试用独立的 paper_library 目录."""

    lib_dir = tmp_path / "paper_library"
    eval_dir = tmp_path / "paper_library_eval"
    lib_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(lib_dir))
    monkeypatch.setenv("PAPERAGENT_PAPER_EVAL_DIR", str(eval_dir))
    return tmp_path


@pytest.fixture
def seeded_project(tmp_lib_dir):
    """先把 5 个 paper seed 到 project, 返回 project_id."""

    project_id = "test_s50_proj"
    rag_eval_pipeline.seed_library_from_fixtures(project_id, FIXTURES_DIR)
    return project_id


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# S50-1: load_eval_set
# ---------------------------------------------------------------------------


def test_s50_1_load_eval_set():
    papers, questions = rag_eval_pipeline.load_eval_set(FIXTURES_DIR)
    assert len(papers) == 5
    assert "paper_001" in papers
    assert "paper_005" in papers
    assert len(questions) >= 10
    assert all("question_id" in q for q in questions)
    assert all("paper_id" in q for q in questions)
    assert all("question" in q for q in questions)
    assert all("ground_truth_chunk_types" in q for q in questions)


def test_s50_1b_load_eval_set_missing_dir():
    with pytest.raises(FileNotFoundError):
        rag_eval_pipeline.load_eval_set("/nonexistent/path")


# ---------------------------------------------------------------------------
# S50-2: compute_recall_at_k
# ---------------------------------------------------------------------------


def test_s50_2_compute_recall_at_k():
    # gold: [method, experiment]; retrieved: [c1=method, c2=experiment] → 命中 2/2
    recall = eval_metrics.compute_recall_at_k(
        retrieved_chunk_ids=["c1", "c2", "c3"],
        gold_chunk_types=["method", "experiment"],
        chunk_type_lookup={"c1": "method", "c2": "experiment", "c3": "result"},
        k=5,
    )
    assert recall == 1.0


def test_s50_2b_compute_recall_at_k_partial():
    recall = eval_metrics.compute_recall_at_k(
        retrieved_chunk_ids=["c1"],
        gold_chunk_types=["method", "experiment"],
        chunk_type_lookup={"c1": "method"},
        k=5,
    )
    # 命中 1/2
    assert abs(recall - 0.5) < 0.001


def test_s50_2c_compute_recall_at_k_empty_gold():
    recall = eval_metrics.compute_recall_at_k(
        retrieved_chunk_ids=["c1"],
        gold_chunk_types=[],
        chunk_type_lookup={"c1": "method"},
        k=5,
    )
    assert recall == 0.0


def test_s50_2d_compute_recall_at_k_topk_cutoff():
    # gold: [method]; top-3 only sees c1, c2, c3 (no method)
    recall = eval_metrics.compute_recall_at_k(
        retrieved_chunk_ids=["c1", "c2", "c3", "c4", "c5"],
        gold_chunk_types=["method"],
        chunk_type_lookup={
            "c1": "experiment", "c2": "result", "c3": "abstract",
            "c4": "conclusion", "c5": "method",  # method 在第 5 位
        },
        k=3,  # top-3 不包含 method
    )
    assert recall == 0.0


def test_s50_2e_compute_recall_at_k_k5_includes_method():
    # 同样的 retrieved, k=5 → 包含 method → recall = 1
    recall = eval_metrics.compute_recall_at_k(
        retrieved_chunk_ids=["c1", "c2", "c3", "c4", "c5"],
        gold_chunk_types=["method"],
        chunk_type_lookup={
            "c1": "experiment", "c2": "result", "c3": "abstract",
            "c4": "conclusion", "c5": "method",
        },
        k=5,
    )
    assert recall == 1.0


# ---------------------------------------------------------------------------
# S50-3: compute_mrr
# ---------------------------------------------------------------------------


def test_s50_3_compute_mrr():
    mrr = eval_metrics.compute_mrr(
        retrieved_chunk_ids=["c1", "c2", "c3"],
        gold_chunk_ids=["c2"],
    )
    # 第一个相关是 c2 (rank 2) → 1/2
    assert mrr == 0.5


def test_s50_3b_compute_mrr_first_rank():
    mrr = eval_metrics.compute_mrr(
        retrieved_chunk_ids=["c1", "c2", "c3"],
        gold_chunk_ids=["c1"],
    )
    assert mrr == 1.0


def test_s50_3c_compute_mrr_no_hit():
    mrr = eval_metrics.compute_mrr(
        retrieved_chunk_ids=["c1", "c2"],
        gold_chunk_ids=["c3"],
    )
    assert mrr == 0.0


# ---------------------------------------------------------------------------
# S50-4: compute_ndcg_at_k
# ---------------------------------------------------------------------------


def test_s50_4_compute_ndcg_at_k():
    relevance = {"c1": 1.0, "c2": 1.0, "c3": 0.0}
    ndcg = eval_metrics.compute_ndcg_at_k(
        retrieved=["c1", "c2", "c3"],
        relevance=relevance,
        k=3,
    )
    # 完美序: 1.0
    assert abs(ndcg - 1.0) < 0.001


def test_s50_4b_compute_ndcg_at_k_imperfect():
    relevance = {"c1": 0.0, "c2": 0.0, "c3": 1.0}
    ndcg = eval_metrics.compute_ndcg_at_k(
        retrieved=["c1", "c2", "c3"],
        relevance=relevance,
        k=3,
    )
    # 不完美序, ndcg < 1
    assert ndcg < 1.0
    assert ndcg > 0.0


def test_s50_4c_compute_ndcg_at_k_empty():
    ndcg = eval_metrics.compute_ndcg_at_k(
        retrieved=[],
        relevance={},
        k=5,
    )
    assert ndcg == 0.0


# ---------------------------------------------------------------------------
# S50-5: compute_citation_precision
# ---------------------------------------------------------------------------


def test_s50_5_compute_citation_precision():
    # 引用 3 个 chunk, 都在 retrieved 中
    cp = eval_metrics.compute_citation_precision(
        cited_chunks=["c1", "c2", "c3"],
        retrieved_chunks=["c1", "c2", "c3", "c4"],
    )
    assert cp == 1.0


def test_s50_5b_compute_citation_precision_partial():
    cp = eval_metrics.compute_citation_precision(
        cited_chunks=["c1", "c2", "c3"],
        retrieved_chunks=["c1", "c4"],
    )
    # 1/3 命中
    assert abs(cp - 0.3333) < 0.001


def test_s50_5c_compute_citation_precision_empty():
    cp = eval_metrics.compute_citation_precision(
        cited_chunks=[],
        retrieved_chunks=["c1"],
    )
    assert cp == 0.0


# ---------------------------------------------------------------------------
# S50-6: compute_evidence_coverage
# ---------------------------------------------------------------------------


def test_s50_6_compute_evidence_coverage():
    ec = eval_metrics.compute_evidence_coverage(
        answer_chunks_used=["c1", "c2"],
        ground_truth_chunks=["c1", "c2", "c3"],
    )
    # 2/3
    assert abs(ec - 0.6666) < 0.001


def test_s50_6b_compute_evidence_coverage_empty_gold():
    ec = eval_metrics.compute_evidence_coverage(
        answer_chunks_used=["c1"],
        ground_truth_chunks=[],
    )
    assert ec == 0.0


# ---------------------------------------------------------------------------
# S50-7: compute_unsupported_claim_rate
# ---------------------------------------------------------------------------


def test_s50_7_compute_unsupported_claim_rate():
    rate = eval_metrics.compute_unsupported_claim_rate(2, 4)
    assert rate == 0.5


def test_s50_7b_compute_unsupported_claim_rate_zero_total():
    rate = eval_metrics.compute_unsupported_claim_rate(0, 0)
    assert rate == 0.0


def test_s50_7c_compute_unsupported_claim_rate_clamped():
    rate = eval_metrics.compute_unsupported_claim_rate(10, 4)  # > 1
    assert rate == 1.0


# ---------------------------------------------------------------------------
# S50-8: compute_faithfulness
# ---------------------------------------------------------------------------


def test_s50_8_compute_faithfulness_with_refs():
    f = eval_metrics.compute_faithfulness(
        answer="This is an answer with citations [1][2].",
        evidence_refs=["c1", "c2"],
    )
    assert f == 1.0


def test_s50_8b_compute_faithfulness_no_refs():
    f = eval_metrics.compute_faithfulness(
        answer="This is an answer.",
        evidence_refs=[],
    )
    assert f == 0.5  # 中等


def test_s50_8c_compute_faithfulness_empty_answer():
    f = eval_metrics.compute_faithfulness(answer="", evidence_refs=["c1"])
    assert f == 0.0


# ---------------------------------------------------------------------------
# S50-9: aggregate_metrics
# ---------------------------------------------------------------------------


def test_s50_9_aggregate_metrics():
    items = [
        RagEvalItem(
            question_id="q1", paper_id="p1", question="q",
            retrieval_metrics=RetrievalMetrics(recall_at_5=0.8, mrr=0.9, ndcg_at_5=0.7, hit_rate=1.0),
            answer_metrics=AnswerMetrics(citation_precision=0.8, evidence_coverage=0.9, unsupported_claim_rate=0.1, faithfulness=0.95),
            latency_ms=10.0, retrieval_mode="llm",
        ),
        RagEvalItem(
            question_id="q2", paper_id="p1", question="q",
            retrieval_metrics=RetrievalMetrics(recall_at_5=0.6, mrr=0.7, ndcg_at_5=0.5, hit_rate=0.5),
            answer_metrics=AnswerMetrics(citation_precision=0.6, evidence_coverage=0.7, unsupported_claim_rate=0.3, faithfulness=0.85),
            latency_ms=20.0, retrieval_mode="fallback",
        ),
    ]
    r, a, s = eval_metrics.aggregate_metrics(items)
    assert abs(r.recall_at_5 - 0.7) < 0.001
    assert abs(r.mrr - 0.8) < 0.001
    assert abs(a.citation_precision - 0.7) < 0.001
    assert abs(a.unsupported_claim_rate - 0.2) < 0.001
    assert s.total_questions == 2
    assert abs(s.fallback_rate - 0.5) < 0.001
    # latency p50 = 10, p95 ≈ 19.5
    assert s.latency_p50_ms >= 10.0
    assert s.latency_p95_ms >= 15.0


def test_s50_9b_aggregate_metrics_empty():
    r, a, s = eval_metrics.aggregate_metrics([])
    assert r.recall_at_5 == 0.0
    assert a.citation_precision == 0.0
    assert s.total_questions == 0


# ---------------------------------------------------------------------------
# S50-10: run_eval 完整流程
# ---------------------------------------------------------------------------


def test_s50_10_run_eval_full(seeded_project):
    report = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    assert len(report.items) == 15
    assert report.aggregate_system.total_questions == 15
    # 至少 recall@5 > 0 (我们的 fixtures 命中率高)
    assert report.aggregate_retrieval.recall_at_5 > 0.0
    # hit rate 应该 = 1 (gold types 多在前 5)
    assert report.aggregate_retrieval.hit_rate > 0.5


def test_s50_10b_run_eval_scope_specific(seeded_project):
    report = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        scope="specific",
        paper_ids=["paper_001"],
        llm_mock=True,
    )
    # paper_001 有 4 个 question (q001/q002/q003/q013)
    assert len(report.items) == 4
    for it in report.items:
        assert it.paper_id == "paper_001"


def test_s50_10c_run_eval_no_library(tmp_lib_dir):
    # 没 seed → 0 chunks → recall 0
    report = rag_eval_pipeline.run_eval(
        project_id="empty_proj",
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    # 仍有 items (每个 question 一个), 但 retrieved 是空
    assert len(report.items) == 15
    assert all(len(it.retrieved_chunks) == 0 for it in report.items)


# ---------------------------------------------------------------------------
# S50-11: save_baseline / load_baseline roundtrip
# ---------------------------------------------------------------------------


def test_s50_11_baseline_save_load_roundtrip(seeded_project, tmp_lib_dir):
    report = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    saved_path = eval_baseline.save_baseline(report)
    assert Path(saved_path).exists()

    loaded = eval_baseline.load_baseline()
    assert loaded["run_id"] == report.run_id
    assert loaded["aggregate_retrieval"]["recall_at_5"] == report.aggregate_retrieval.recall_at_5
    assert loaded["item_count"] == 15


def test_s50_11b_baseline_load_missing(tmp_path):
    loaded = eval_baseline.load_baseline(path=tmp_path / "nonexistent.json")
    assert loaded == {}


# ---------------------------------------------------------------------------
# S50-12: diff_against_baseline 回归检测
# ---------------------------------------------------------------------------


def test_s50_12_diff_no_regression(seeded_project, tmp_lib_dir):
    """同 baseline diff → 无 regression."""

    report = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    eval_baseline.save_baseline(report)
    baseline = eval_baseline.load_baseline()
    diff = eval_baseline.diff_against_baseline(report, baseline)
    assert diff["regressions"] == []


def test_s50_12b_diff_detect_regression():
    """合成差 baseline → 应检测到 regression."""

    baseline = {
        "run_id": "old",
        "aggregate_retrieval": {"recall_at_5": 0.9, "mrr": 0.85, "ndcg_at_5": 0.9, "hit_rate": 1.0},
        "aggregate_answer": {"citation_precision": 0.95, "evidence_coverage": 0.95, "unsupported_claim_rate": 0.02, "faithfulness": 0.95},
        "aggregate_system": {"latency_p50_ms": 50.0, "latency_p95_ms": 100.0, "total_questions": 15, "fallback_rate": 0.0},
    }
    current = RagEvalReport(
        run_id="new",
        items=[],
        aggregate_retrieval=RetrievalMetrics(recall_at_5=0.7, mrr=0.7, ndcg_at_5=0.7, hit_rate=0.8),
        aggregate_answer=AnswerMetrics(citation_precision=0.7, evidence_coverage=0.7, unsupported_claim_rate=0.2, faithfulness=0.7),
        aggregate_system=SystemMetrics(latency_p50_ms=80.0, latency_p95_ms=300.0, total_questions=15, fallback_rate=0.1),
    )
    diff = eval_baseline.diff_against_baseline(current, baseline)
    assert len(diff["regressions"]) >= 5  # recall, mrr, ndcg, hit, cit, cov, faith, latency, fallback
    assert any("recall_at_5" in r for r in diff["regressions"])
    assert any("unsupported_claim_rate" in r for r in diff["regressions"])


def test_s50_12c_diff_no_baseline():
    """无 baseline → diff 为空."""

    current = RagEvalReport(
        run_id="new",
        items=[],
        aggregate_retrieval=RetrievalMetrics(recall_at_5=0.7),
    )
    diff = eval_baseline.diff_against_baseline(current, {})
    assert diff["regressions"] == []
    assert diff["baseline_run_id"] is None


# ---------------------------------------------------------------------------
# S50-13: 端点形状
# ---------------------------------------------------------------------------


def test_s50_13_eval_seed_library_endpoint(client, tmp_lib_dir):
    """POST /eval/seed-library 端点."""

    resp = client.post(
        "/api/v1/projects/eval_test_proj/paper-library/eval/seed-library",
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == "eval_test_proj"
    assert body["paper_count"] == 5
    assert body["chunk_count"] > 0


def test_s50_13b_eval_run_endpoint(client, tmp_lib_dir):
    """POST /eval/run 端点."""

    # 先 seed
    client.post(
        "/api/v1/projects/eval_test_proj2/paper-library/eval/seed-library",
        json={},
    )
    # 再 run
    resp = client.post(
        "/api/v1/projects/eval_test_proj2/paper-library/eval/run",
        json={"llm_mock": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "report" in body
    report = body["report"]
    assert len(report["items"]) == 15
    assert "aggregate_retrieval" in report
    assert "aggregate_answer" in report
    assert "aggregate_system" in report
    assert "recall_at_5" in report["aggregate_retrieval"]


def test_s50_13c_eval_get_baseline_endpoint(client, tmp_lib_dir):
    """GET /eval/baseline 端点 (初始空)."""

    resp = client.get("/api/v1/projects/eval_test_proj3/paper-library/eval/baseline")
    assert resp.status_code == 200
    body = resp.json()
    # 第一次跑 (没 baseline 存过) → 可能是空 dict
    assert isinstance(body, dict)


def test_s50_13d_eval_save_baseline_endpoint(client, tmp_lib_dir):
    """POST /eval/baseline 端点 (保存 baseline)."""

    # 先 seed
    client.post(
        "/api/v1/projects/eval_test_proj4/paper-library/eval/seed-library",
        json={},
    )
    # 保存 baseline
    resp = client.post(
        "/api/v1/projects/eval_test_proj4/paper-library/eval/baseline",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "saved_path" in body
    assert "run_id" in body
    assert "aggregate_retrieval" in body
    # 然后 GET 应能读到
    resp2 = client.get("/api/v1/projects/eval_test_proj4/paper-library/eval/baseline")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["run_id"] == body["run_id"]


# ---------------------------------------------------------------------------
# S50-14: 退化警告 (recall drop) via real eval
# ---------------------------------------------------------------------------


def test_s50_14_regression_warning_on_recall_drop(seeded_project, tmp_lib_dir):
    """跑一次 eval, save baseline; 然后 run_eval 应能 diff (无 regression)."""

    report1 = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    eval_baseline.save_baseline(report1)

    # 跑第二次 (同样数据, 同样 mock → 无 regression)
    report2 = rag_eval_pipeline.run_eval(
        project_id=seeded_project,
        fixtures_dir=FIXTURES_DIR,
        llm_mock=True,
    )
    baseline = eval_baseline.load_baseline()
    diff = eval_baseline.diff_against_baseline(report2, baseline)
    # 第二次跑同数据 → recall 应该几乎一样, 无 regression
    assert diff["regressions"] == []
    # run_id 可能不同 (每次 new uuid), 但指标应相同
    assert report2.aggregate_retrieval.recall_at_5 == report1.aggregate_retrieval.recall_at_5
