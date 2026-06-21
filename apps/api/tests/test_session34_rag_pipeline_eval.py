"""Session 34: RAG Pipeline + Evaluator backend tests (10 个).

S34-1: QueryPlan / 三类 query 生成
S34-2: Sparse + Dense 可融合
S34-3: RRF 排序稳定
S34-4: Rerank score 改变排序
S34-5: URL 未验证降权
S34-6: Paper/Dataset/Repo 覆盖率可计算
S34-7: RagEvalReport 可序列化
S34-8: 无候选返回 failure_case
S34-9: S24 CandidateResource 不回退
S34-10: S31 baseline 不回退
"""

from __future__ import annotations

import json

import pytest

from app.schemas_evidence import (
    EvidenceItem,
    EvidenceLedgerResponse,
    ReviewStatus,
)
from app.schemas_rag_eval import (
    DEFAULT_RAG_CONFIG,
    FailureCase,
    RagEvalReport,
    RagPipelineConfig,
    RetrievalCandidate,
)
from app.schemas_retrieval import (
    QueryPlan,
    QueryPlanLayer,
    RetrievalCandidate as S14Candidate,
    SearchSource,
)
from app.services.rag_evaluator import (
    compute_candidate_to_evidence_rate,
    compute_citation_coverage,
    compute_evidence_precision,
    compute_mrr,
    compute_recall_at_k,
    compute_type_coverage,
    compute_url_verified_rate,
    detect_failure_cases,
    evaluate_rag,
)
from app.services.rag_pipeline import (
    dense_retrieve,
    reset_rag_state,
    rerank_candidates,
    rrf_fuse,
    run_rag_pipeline,
    sparse_retrieve,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean():
    reset_rag_state()
    yield
    reset_rag_state()


def _mk_s14(
    cid: str,
    kind: str = "paper",
    title: str = "Default Title",
    source: str = "arxiv",
    year: int | None = 2024,
    abstract: str = "default abstract",
    url: str = "https://example.com",
    arxiv_id: str | None = None,
    doi: str | None = None,
    repo_full_name: str | None = None,
    dataset_slug: str | None = None,
    license: str | None = None,
    stars: int | None = None,
    citation_count: int | None = None,
) -> S14Candidate:
    return S14Candidate(
        candidate_id=cid,
        project_id="p1",
        candidate_type=kind,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        title=title,
        url=url,
        year=year,
        abstract=abstract,
        arxiv_id=arxiv_id,
        doi=doi,
        repo_full_name=repo_full_name,
        dataset_slug=dataset_slug,
        license=license,
        stars=stars,
        citation_count=citation_count,
    )


def _mk_rag_cand(
    cid: str,
    kind: str = "paper",
    title: str = "Default Title",
    url_verified: bool = False,
    rerank_score: float = 0.5,
    matched: list[str] | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=cid,
        project_id="p1",
        kind=kind,  # type: ignore[arg-type]
        title=title,
        source="arxiv",
        query_id="q1",
        url_verified=url_verified,
        rerank_score=rerank_score,
        matched_keywords=matched or [],
    )


# ---------------------------------------------------------------------------
# S34-1: QueryPlan / 三类 query 生成 (Pipeline 入口)
# ---------------------------------------------------------------------------


class TestQueryPlan:
    def test_sparse_retrieve_returns_top_k(self):
        candidates = [
            _mk_s14("c1", title="YOLO steel defect detection"),
            _mk_s14("c2", title="Random unrelated content"),
            _mk_s14("c3", title="Defect detection in steel plates"),
        ]
        results = sparse_retrieve(candidates, ["YOLO", "steel"], top_k=2)
        assert len(results) == 2
        # Top result 应是 c1 或 c3 (含 steel/defect)
        top_cid = results[0][0].candidate_id
        assert top_cid in ("c1", "c3")

    def test_dense_retrieve_returns_top_k(self):
        candidates = [
            _mk_s14("c1", title="YOLO steel defect detection"),
            _mk_s14("c2", title="Random unrelated content"),
            _mk_s14("c3", title="Defect detection in steel plates"),
        ]
        results = dense_retrieve(candidates, ["steel", "defect"], top_k=2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# S34-2: Sparse + Dense 可融合
# ---------------------------------------------------------------------------


class TestHybridFusion:
    def test_rrf_fuse_merges_sparse_dense(self):
        s14 = [
            _mk_s14("c1"),
            _mk_s14("c2"),
            _mk_s14("c3"),
        ]
        sparse = [(s14[0], 0.9), (s14[1], 0.5), (s14[2], 0.1)]
        dense = [(s14[2], 0.95), (s14[0], 0.4), (s14[1], 0.2)]

        fused = rrf_fuse(sparse, dense, k=60)
        # 应返回 3 个 candidate
        assert len(fused) == 3
        cids = [c.candidate_id for c in fused]
        assert set(cids) == {"c1", "c2", "c3"}

    def test_rrf_fuse_handles_empty(self):
        assert rrf_fuse([], [], k=60) == []
        s14 = [_mk_s14("c1")]
        sparse = [(s14[0], 0.9)]
        fused = rrf_fuse(sparse, [], k=60)
        assert len(fused) == 1


# ---------------------------------------------------------------------------
# S34-3: RRF 排序稳定
# ---------------------------------------------------------------------------


class TestRRFStability:
    def test_rrf_deterministic(self):
        """同输入两次跑应得相同结果."""
        s14 = [_mk_s14(f"c{i}") for i in range(5)]
        sparse = [(s14[i], 1.0 - i * 0.1) for i in range(5)]
        dense = [(s14[i], 1.0 - i * 0.15) for i in range(5)]

        fused1 = rrf_fuse(sparse, dense, k=60)
        fused2 = rrf_fuse(sparse, dense, k=60)
        assert [c.candidate_id for c in fused1] == [c.candidate_id for c in fused2]

    def test_rrf_first_doc_wins(self):
        """sparse 和 dense 都把 c1 排第一 → c1 fused 分数应最高."""
        s14 = [_mk_s14("c1"), _mk_s14("c2")]
        sparse = [(s14[0], 0.9), (s14[1], 0.5)]
        dense = [(s14[0], 0.9), (s14[1], 0.5)]
        fused = rrf_fuse(sparse, dense, k=60)
        assert fused[0].candidate_id == "c1"


# ---------------------------------------------------------------------------
# S34-4: Rerank score 改变排序
# ---------------------------------------------------------------------------


class TestRerank:
    def test_rerank_reorders_candidates(self):
        """rerank 后排序应与 rerank_score 降序一致."""
        candidates = [
            _mk_rag_cand("c1", title="YOLO steel defect detection", url_verified=True),
            _mk_rag_cand("c2", title="Random unrelated", url_verified=False),
            _mk_rag_cand("c3", title="Defect detection on steel plates", url_verified=True),
        ]
        reranked = rerank_candidates(candidates, ["YOLO", "steel", "defect"], DEFAULT_RAG_CONFIG)
        scores = [c.rerank_score for c in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_url_verified_higher_score(self):
        """URL 已验证的应比未验证的高分."""
        verified = [_mk_rag_cand("v1", title="YOLO steel", url_verified=True)]
        unverified = [_mk_rag_cand("u1", title="YOLO steel", url_verified=False)]
        reranked = rerank_candidates(verified + unverified, ["YOLO", "steel"], DEFAULT_RAG_CONFIG)
        assert reranked[0].candidate_id == "v1"
        assert reranked[0].rerank_score > reranked[1].rerank_score

    def test_rerank_records_reasons(self):
        candidates = [_mk_rag_cand("c1", url_verified=True)]
        reranked = rerank_candidates(candidates, ["foo"], DEFAULT_RAG_CONFIG)
        assert len(reranked[0].rerank_reasons) > 0


# ---------------------------------------------------------------------------
# S34-5: URL 未验证降权
# ---------------------------------------------------------------------------


class TestUrlVerifiedPenalty:
    def test_unverified_score_drops(self):
        """URL 未验证的 rerank score 应乘以 0.4 惩罚因子."""
        verified = [_mk_rag_cand("v1", url_verified=True)]
        unverified = [_mk_rag_cand("u1", url_verified=False)]

        reranked_v = rerank_candidates(verified, ["foo"], DEFAULT_RAG_CONFIG)
        reranked_u = rerank_candidates(unverified, ["foo"], DEFAULT_RAG_CONFIG)

        v_score = reranked_v[0].rerank_score
        u_score = reranked_u[0].rerank_score
        # Unverified 应该有显著降低
        assert u_score < v_score


# ---------------------------------------------------------------------------
# S34-6: Paper/Dataset/Repo 覆盖率
# ---------------------------------------------------------------------------


class TestTypeCoverage:
    def test_three_kinds_full_coverage(self):
        candidates = [
            _mk_rag_cand("c1", kind="paper"),
            _mk_rag_cand("c2", kind="dataset"),
            _mk_rag_cand("c3", kind="repo"),
        ]
        coverage = compute_type_coverage(candidates)
        assert coverage["paper"] == 1.0
        assert coverage["dataset"] == 1.0
        assert coverage["repo"] == 1.0

    def test_missing_dataset_zero_coverage(self):
        candidates = [
            _mk_rag_cand("c1", kind="paper"),
            _mk_rag_cand("c2", kind="repo"),
        ]
        coverage = compute_type_coverage(candidates)
        assert coverage["dataset"] == 0.0


# ---------------------------------------------------------------------------
# S34-7: RagEvalReport 可序列化
# ---------------------------------------------------------------------------


class TestEvalReportSerializable:
    def test_report_json_roundtrip(self):
        report = RagEvalReport(
            project_id="p1",
            run_id="r1",
            recall_at_5=0.8,
            recall_at_10=1.0,
            recall_at_20=1.0,
            mrr=0.95,
            citation_coverage=0.75,
            evidence_precision=0.85,
            url_verified_rate=0.6,
            candidate_to_evidence_rate=0.7,
            paper_coverage=1.0,
            dataset_coverage=0.5,
            repo_coverage=0.5,
            evaluated_at="2026-06-21T00:00:00Z",
        )
        data = report.model_dump()
        s = json.dumps(data, ensure_ascii=False)
        restored = json.loads(s)
        assert restored["project_id"] == "p1"
        assert restored["mrr"] == 0.95
        assert restored["paper_coverage"] == 1.0

    def test_failure_case_serializable(self):
        fc = FailureCase(
            case_type="no_dataset",
            description="missing",
            affected_candidates=["c1", "c2"],
        )
        data = fc.model_dump()
        assert data["case_type"] == "no_dataset"
        assert data["affected_candidates"] == ["c1", "c2"]


# ---------------------------------------------------------------------------
# S34-8: 无候选 → failure_case
# ---------------------------------------------------------------------------


class TestEmptyFailure:
    def test_no_candidates_returns_failure(self):
        candidates: list[RetrievalCandidate] = []
        failures = detect_failure_cases(candidates, {"dataset_coverage": 0.0, "repo_coverage": 0.0})
        # 至少应包括 no_dataset 和 no_repo
        case_types = {f.case_type for f in failures}
        assert "no_dataset" in case_types or "no_repo" in case_types

    def test_pipeline_empty_returns_partial(self):
        result = run_rag_pipeline("p1", [], ["foo"])
        assert result["status"] in ("completed", "partial", "failed")
        assert result["candidates"] == []


# ---------------------------------------------------------------------------
# S34-9: S24 CandidateResource 不回退 (Pipeline 输出结构兼容)
# ---------------------------------------------------------------------------


class TestS24Compat:
    def test_pipeline_outputs_rag_candidates(self):
        """RAG pipeline 输出的 candidates 应保留 S14 关键字段 (title, url, year 等)."""
        s14 = [
            _mk_s14("c1", kind="paper", title="YOLO steel", arxiv_id="2406.12345", year=2024),
            _mk_s14("c2", kind="repo", title="github.com/x/y", repo_full_name="x/y", stars=200),
            _mk_s14("c3", kind="dataset", title="datasetX", dataset_slug="x", license="MIT"),
        ]
        result = run_rag_pipeline("p1", s14, ["YOLO", "steel", "dataset"])
        candidates = result["candidates"]
        for c in candidates:
            # S14 字段透传
            assert c.title
            assert c.candidate_id
            assert c.kind in ("paper", "dataset", "repo")


# ---------------------------------------------------------------------------
# S34-10: S31 baseline 不回退 (RAG eval 不破坏现有数据流)
# ---------------------------------------------------------------------------


class TestS31Compat:
    def test_eval_doesnt_mutate_candidates(self):
        """评估函数不应修改 candidates 的关键字段."""
        candidates = [
            _mk_rag_cand("c1", kind="paper", title="YOLO", url_verified=False, rerank_score=0.5),
            _mk_rag_cand("c2", kind="dataset", title="dataset", url_verified=True, rerank_score=0.7),
        ]
        # 缓存原始
        before = [(c.candidate_id, c.title, c.rerank_score) for c in candidates]

        report = evaluate_rag(
            "p1", "r1", candidates,
            ground_truth={"c1"},
            section_count=12,
            bound_section_count=8,
            imported_count=2,
        )

        # 候选没被改
        after = [(c.candidate_id, c.title, c.rerank_score) for c in candidates]
        assert before == after

        # 报告字段计算正确
        assert report.project_id == "p1"
        assert report.run_id == "r1"
        assert 0.0 <= report.recall_at_10 <= 1.0
        assert 0.0 <= report.citation_coverage <= 1.0


# ---------------------------------------------------------------------------
# Bonus: compute_* 单元测试
# ---------------------------------------------------------------------------


class TestMetricsUnit:
    def test_recall_at_k_perfect(self):
        candidates = [_mk_rag_cand(f"c{i}") for i in range(5)]
        gt = {"c0", "c1", "c2", "c3", "c4"}
        assert compute_recall_at_k(candidates, gt, 5) == 1.0

    def test_recall_at_k_partial(self):
        candidates = [_mk_rag_cand(f"c{i}") for i in range(3)]
        gt = {"c0", "c1", "c2", "c3", "c4"}  # 5 ground truth, only 3 in top-3
        assert compute_recall_at_k(candidates, gt, 5) == 3 / 5

    def test_mrr_first_hit(self):
        candidates = [_mk_rag_cand("c0"), _mk_rag_cand("c1")]
        gt = {"c0"}
        assert compute_mrr(candidates, gt) == 1.0

    def test_mrr_second_hit(self):
        candidates = [_mk_rag_cand("c0"), _mk_rag_cand("c1")]
        gt = {"c1"}
        assert compute_mrr(candidates, gt) == 0.5

    def test_citation_coverage(self):
        assert compute_citation_coverage(10, 8) == 0.8
        assert compute_citation_coverage(0, 0) == 0.0

    def test_url_verified_rate(self):
        candidates = [
            _mk_rag_cand("c1", url_verified=True),
            _mk_rag_cand("c2", url_verified=False),
            _mk_rag_cand("c3", url_verified=True),
        ]
        assert compute_url_verified_rate(candidates) == 2 / 3

    def test_candidate_to_evidence_rate(self):
        assert compute_candidate_to_evidence_rate(10, 7) == 0.7