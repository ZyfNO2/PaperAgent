"""Session 61 M5: RetrievalGapReport.

Aggregates paper/dataset/repo candidate counts + per-source ``SourceResult``s
into a structured ``GapReport``. Distinguishes ``source_failed`` from
``no_result`` via ``source_policy.classify_run_result``.

Ponytail: no LLM, deterministic strings, single summary paragraph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ...schemas_retrieval import CandidateType, SourceResult
from .source_policy import classify_completion


GapCategory = Literal[
    "no_paper",
    "no_dataset",
    "no_repo",
    "low_quality",
    "source_failed",
    "query_too_narrow",
    "adapter_missing",
]


@dataclass
class GapItem:
    category: GapCategory
    details: str


@dataclass
class GapReport:
    gaps: list[GapItem] = field(default_factory=list)
    next_step_queries: list[str] = field(default_factory=list)
    summary_text: str = ""


# 缺类默认下一步 query 模板
_NEXT_STEP_HINTS: dict[str, list[str]] = {
    "no_paper": ["{topic} survey", "{topic} benchmark"],
    "no_dataset": [
        "{topic} crack detection dataset",
        "{topic} structural health monitoring dataset",
        "{topic} benchmark HuggingFace",
    ],
    "no_repo": [
        "{topic} 3D damage detection github pytorch",
        "{topic} baseline code implementation",
    ],
}


def _has_failure(source_results: list[SourceResult], candidate_type: CandidateType) -> str | None:
    expected = {
        "paper": ["openalex", "arxiv"],
        "dataset": ["huggingface", "kaggle"],
        "repo": ["github"],
    }.get(candidate_type, [])
    if not expected:
        return None
    rel = [s for s in source_results if s.source in expected]
    if not rel:
        return "adapter_missing"
    if all(s.status == "failed" for s in rel):
        return "source_failed"
    return None


def build_gap_report(
    paper_n: int,
    dataset_n: int,
    repo_n: int,
    source_results: list[SourceResult],
    candidate_type_counts: dict[CandidateType, int] | None = None,
) -> GapReport:
    """根据候选数量 + 各 source 的执行状态生成缺口报告."""

    counts = candidate_type_counts or {}
    paper_n = counts.get("paper", paper_n)
    dataset_n = counts.get("dataset", dataset_n)
    repo_n = counts.get("repo", repo_n)

    gaps: list[GapItem] = []
    next_queries: list[str] = []
    placeholder = "{topic}"

    # ----- 来源失败 / adapter 缺失 ----- #
    for ct, n in (("paper", paper_n), ("dataset", dataset_n), ("repo", repo_n)):
        reason = _has_failure(source_results, ct) if n == 0 else None
        if reason == "source_failed":
            gaps.append(GapItem(
                category="source_failed",
                details=f"{ct} 来源全部失败, 网络或 API 不可达",
            ))
        elif reason == "adapter_missing":
            gaps.append(GapItem(
                category="adapter_missing",
                details=f"{ct} 未配置对应 adapter 或 adapter 未返回任何结果",
            ))

    # ----- 数量缺口 ----- #
    if paper_n == 0:
        gaps.append(GapItem(category="no_paper", details="未找到任何论文候选"))
        next_queries.extend([
            t.replace(placeholder, "本课题") for t in _NEXT_STEP_HINTS["no_paper"]
        ])

    if dataset_n == 0:
        gaps.append(GapItem(category="no_dataset", details="未找到任何公开数据集候选"))
        next_queries.extend([
            t.replace(placeholder, "本课题") for t in _NEXT_STEP_HINTS["no_dataset"]
        ])

    if repo_n == 0:
        gaps.append(GapItem(category="no_repo", details="未找到任何可复现工程候选"))
        next_queries.extend([
            t.replace(placeholder, "本课题") for t in _NEXT_STEP_HINTS["no_repo"]
        ])

    # ----- 低质量: 有候选但全部低分 ----- #
    # ponytail: 不实现复杂质量计算; 若三类型都极低, 提示低质量
    # 这里只作为可选信号, 暂时不强制

    # ----- summary ----- #
    if not gaps:
        summary_text = (
            f"三类候选均已就绪 (paper={paper_n}, dataset={dataset_n}, repo={repo_n}); "
            "无需补搜。"
        )
    else:
        bits = []
        if paper_n == 0:
            bits.append("论文候选为空")
        if dataset_n == 0:
            bits.append("数据集候选为空")
        if repo_n == 0:
            bits.append("工程候选为空")
        any_failed = any(g.category in ("source_failed", "adapter_missing") for g in gaps)
        verb = "失败" if any_failed else "未找到"
        summary_text = (
            f"本次检索{'/'.join(bits) or '存在缺口'}: "
            f"{verb} {len(gaps)} 类问题 (paper={paper_n}, dataset={dataset_n}, repo={repo_n}). "
            "已生成补搜建议, 可执行一轮 retry。"
        )

    # 去重保序
    seen: set[str] = set()
    deduped_qs: list[str] = []
    for q in next_queries:
        q = (q or "").strip()
        if q and q not in seen:
            seen.add(q)
            deduped_qs.append(q)

    return GapReport(
        gaps=gaps,
        next_step_queries=deduped_qs,
        summary_text=summary_text,
    )


if __name__ == "__main__":
    # ponytail: self-check
    from ...schemas_retrieval import SourceResult as _SR

    failed = [
        _SR(source="openalex", status="failed", candidate_count=0, error="net"),
        _SR(source="arxiv", status="failed", candidate_count=0, error="net"),
        _SR(source="huggingface", status="failed", candidate_count=0, error="net"),
        _SR(source="kaggle", status="failed", candidate_count=0, error="net"),
        _SR(source="github", status="failed", candidate_count=0, error="net"),
    ]

    g = build_gap_report(0, 0, 0, failed)
    cats = [x.category for x in g.gaps]
    assert "source_failed" in cats, cats
    assert "no_paper" in cats, cats
    assert "no_dataset" in cats, cats
    assert "no_repo" in cats, cats
    assert g.next_step_queries, "next_step_queries empty"
    assert ("失败" in g.summary_text or "未找到" in g.summary_text), g.summary_text

    print(f"OK gap_report self-check passed (gaps={len(g.gaps)}, qs={len(g.next_step_queries)})")