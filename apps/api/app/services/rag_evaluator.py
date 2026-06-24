"""Session 34: RAG Evaluator — Recall@K / MRR / Citation Coverage / Evidence Precision.

面试可讲：
- Recall@K = (前 K 个里相关数) / (总相关数)
- MRR = 1 / rank_of_first_relevant
- Citation Coverage = 报告章节中绑定了 evidence_ref 的比例
- Evidence Precision = 引用了 evidence 的章节中, evidence 是 accepted/core 的比例
- URL Verified Rate = url_verified=True 的比例
- Candidate → Evidence Rate = imported/imported_total

注意 (S50 关系):
- S34 是 metadata-level RAG 评估: 评估对象是 RetrievalCandidate (论文/数据集/仓库/笔记) 的
  检索质量与 Evidence Ledger 覆盖率, 用于 RAG 检索 skill 的端到端验证.
- S50 是 paper-library level RAG 评估: 评估对象是 paper chunk 切块 + paper_qa 问答
  (apps/api/app/services/paper_library/eval_metrics.py), 用于论文库问答系统的回归基线.
- 两者不共享代码 (并行存在): S34 操作 RetrievalCandidate 列表 + Evidence Ledger,
  S50 操作 PaperChunk 列表 + ground truth question set + baseline.json.
- 如需统一, 应抽取一个公共层 (chunk/candidate 中间抽象), 但当前 S50 fixture 与 S34 metadata
  schema 不同, 重构成本 > 收益, 故保持并行.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..schemas_evidence import EvidenceItem, EvidenceLedgerResponse, ReviewStatus
from ..schemas_rag_eval import (
    DEFAULT_RAG_CONFIG,
    FailureCase,
    RagEvalReport,
    RagPipelineConfig,
    RetrievalCandidate,
)


# ---------------------------------------------------------------------------
# Recall@K
# ---------------------------------------------------------------------------


def _is_relevant(cand: RetrievalCandidate, ground_truth: set[str]) -> bool:
    """候选是否在 ground_truth 集合内.

    ground_truth 是 evidence_id 集合 / candidate_id 集合 / url 集合.
    """
    if not ground_truth:
        return False
    if cand.candidate_id in ground_truth:
        return True
    if cand.url and cand.url in ground_truth:
        return True
    if cand.doi and cand.doi in ground_truth:
        return True
    if cand.arxiv_id and cand.arxiv_id in ground_truth:
        return True
    return False


def compute_recall_at_k(
    candidates: list[RetrievalCandidate],
    ground_truth: set[str],
    k: int,
) -> float:
    """Recall@K = 前 K 个里相关数 / 总相关数."""
    if not ground_truth:
        return 0.0
    top_k = candidates[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for c in top_k if _is_relevant(c, ground_truth))
    return min(1.0, hits / len(ground_truth))


# ---------------------------------------------------------------------------
# MRR (Mean Reciprocal Rank)
# ---------------------------------------------------------------------------


def compute_mrr(
    candidates: list[RetrievalCandidate],
    ground_truth: set[str],
) -> float:
    """MRR = 1 / 第一个相关候选的 rank (1-indexed)."""
    if not ground_truth:
        return 0.0
    for rank, cand in enumerate(candidates, start=1):
        if _is_relevant(cand, ground_truth):
            return 1.0 / rank
    return 0.0


# ---------------------------------------------------------------------------
# Citation Coverage
# ---------------------------------------------------------------------------


def compute_citation_coverage(
    section_count: int,
    bound_section_count: int,
) -> float:
    """报告章节中绑定了 evidence_ref 的比例."""
    if section_count == 0:
        return 0.0
    return min(1.0, bound_section_count / section_count)


# ---------------------------------------------------------------------------
# Evidence Precision
# ---------------------------------------------------------------------------


def compute_evidence_precision(
    ledger: Optional[EvidenceLedgerResponse],
    cited_evidence_ids: set[str],
) -> float:
    """被引用的 evidence 中, accepted/core 的比例.

    高引用 + 高质量 = 高 evidence precision.
    """
    if not cited_evidence_ids:
        return 0.0
    if ledger is None:
        return 0.0

    all_items: list[EvidenceItem] = [
        *ledger.papers,
        *ledger.datasets,
        *ledger.repos,
        *ledger.notes,
    ]
    by_id = {item.evidence_id: item for item in all_items}

    good_status = {ReviewStatus.accepted.value, ReviewStatus.core.value, "background"}
    hits = 0
    for eid in cited_evidence_ids:
        item = by_id.get(eid)
        if item is None:
            continue
        if item.review_status in good_status:
            hits += 1
    return min(1.0, hits / len(cited_evidence_ids)) if cited_evidence_ids else 0.0


# ---------------------------------------------------------------------------
# URL Verified Rate
# ---------------------------------------------------------------------------


def compute_url_verified_rate(candidates: list[RetrievalCandidate]) -> float:
    """url_verified=True 的比例."""
    if not candidates:
        return 0.0
    verified = sum(1 for c in candidates if c.url_verified)
    return min(1.0, verified / len(candidates))


# ---------------------------------------------------------------------------
# Candidate → Evidence Rate
# ---------------------------------------------------------------------------


def compute_candidate_to_evidence_rate(
    candidate_count: int,
    imported_count: int,
) -> float:
    """imported / total candidates."""
    if candidate_count == 0:
        return 0.0
    return min(1.0, imported_count / candidate_count)


# ---------------------------------------------------------------------------
# Type Coverage
# ---------------------------------------------------------------------------


def compute_type_coverage(
    candidates: list[RetrievalCandidate],
    expected_kinds: set[str] | None = None,
) -> dict[str, float]:
    """每种类型的覆盖率 (1.0 = 至少 1 个)."""
    expected = expected_kinds or {"paper", "dataset", "repo"}
    if not candidates:
        return {k: 0.0 for k in expected}

    found: set[str] = {c.kind for c in candidates}
    return {kind: 1.0 if kind in found else 0.0 for kind in expected}


# ---------------------------------------------------------------------------
# Failure Cases
# ---------------------------------------------------------------------------


def detect_failure_cases(
    candidates: list[RetrievalCandidate],
    eval_partial: dict[str, float],
) -> list[FailureCase]:
    """从候选和评估结果中发现失败案例."""
    failures: list[FailureCase] = []

    # 1. 无 dataset
    if eval_partial.get("dataset_coverage", 1.0) < 0.5:
        failures.append(
            FailureCase(
                case_type="no_dataset",
                description="未检索到符合条件的数据集，建议补充人工添加或调整关键词",
                affected_candidates=[c.candidate_id for c in candidates if c.kind == "paper"],
            )
        )

    # 2. 无 repo
    if eval_partial.get("repo_coverage", 1.0) < 0.5:
        failures.append(
            FailureCase(
                case_type="no_repo",
                description="未检索到可复现的代码仓库，建议引导用户手动添加或切换关键词",
                affected_candidates=[],
            )
        )

    # 3. URL 未验证
    unverified = [c.candidate_id for c in candidates if not c.url_verified]
    if unverified and len(unverified) / max(1, len(candidates)) > 0.5:
        failures.append(
            FailureCase(
                case_type="url_unverified",
                description=f"{len(unverified)} 个候选 URL 未验证，建议运行 verification gate",
                affected_candidates=unverified,
            )
        )

    # 4. 类型不均衡
    type_counts: dict[str, int] = {}
    for c in candidates:
        type_counts[c.kind] = type_counts.get(c.kind, 0) + 1
    if type_counts:
        max_share = max(type_counts.values()) / max(1, len(candidates))
        if max_share > 0.85:
            dominant = [k for k, v in type_counts.items() if v / max(1, len(candidates)) == max_share]
            failures.append(
                FailureCase(
                    case_type="type_imbalance",
                    description=f"检索结果中 {dominant} 类型占 {max_share:.0%}，建议补充其他类型证据",
                    affected_candidates=[c.candidate_id for c in candidates if c.kind in dominant],
                )
            )

    # 5. 低相关性
    low_rel = [c for c in candidates if c.rerank_score < 0.3]
    if low_rel and len(low_rel) / max(1, len(candidates)) > 0.5:
        failures.append(
            FailureCase(
                case_type="low_relevance",
                description=f"{len(low_rel)} 个候选 rerank_score < 0.3，建议重新生成查询计划",
                affected_candidates=[c.candidate_id for c in low_rel],
            )
        )

    return failures


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------


def evaluate_rag(
    project_id: str,
    run_id: str,
    candidates: list[RetrievalCandidate],
    *,
    ground_truth: Optional[set[str]] = None,
    ledger: Optional[EvidenceLedgerResponse] = None,
    cited_evidence_ids: Optional[set[str]] = None,
    section_count: int = 0,
    bound_section_count: int = 0,
    imported_count: int = 0,
    config: Optional[RagPipelineConfig] = None,
) -> RagEvalReport:
    """生成完整 RAG 评估报告."""
    cfg = config or DEFAULT_RAG_CONFIG
    gt = ground_truth or set()

    # Recall@K
    recall_at_5 = compute_recall_at_k(candidates, gt, 5)
    recall_at_10 = compute_recall_at_k(candidates, gt, 10)
    recall_at_20 = compute_recall_at_k(candidates, gt, 20)

    # MRR
    mrr = compute_mrr(candidates, gt)

    # Citation Coverage
    citation_coverage = compute_citation_coverage(section_count, bound_section_count)

    # Evidence Precision
    evidence_precision = compute_evidence_precision(ledger, cited_evidence_ids or set())

    # URL Verified Rate
    url_verified_rate = compute_url_verified_rate(candidates)

    # Candidate → Evidence Rate
    candidate_to_evidence_rate = compute_candidate_to_evidence_rate(
        len(candidates), imported_count
    )

    # Type Coverage
    type_coverage = compute_type_coverage(candidates)
    paper_cov = type_coverage.get("paper", 0.0)
    dataset_cov = type_coverage.get("dataset", 0.0)
    repo_cov = type_coverage.get("repo", 0.0)

    # Failure cases
    eval_partial = {
        "dataset_coverage": dataset_cov,
        "repo_coverage": repo_cov,
    }
    failure_cases = detect_failure_cases(candidates, eval_partial)

    return RagEvalReport(
        project_id=project_id,
        run_id=run_id,
        recall_at_5=round(recall_at_5, 4),
        recall_at_10=round(recall_at_10, 4),
        recall_at_20=round(recall_at_20, 4),
        mrr=round(mrr, 4),
        citation_coverage=round(citation_coverage, 4),
        evidence_precision=round(evidence_precision, 4),
        url_verified_rate=round(url_verified_rate, 4),
        candidate_to_evidence_rate=round(candidate_to_evidence_rate, 4),
        paper_coverage=round(paper_cov, 4),
        dataset_coverage=round(dataset_cov, 4),
        repo_coverage=round(repo_cov, 4),
        failure_cases=failure_cases,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        config_snapshot=cfg,
    )