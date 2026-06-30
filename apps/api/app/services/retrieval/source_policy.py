"""Session 61 M2: RetrievalSourcePolicy.

Maps candidate types to the set of allowed ``SearchSource`` values, and
classifies a run's per-source results into a single ``FailureReason`` for
downstream gap_report consumption. Pure constants + small classifier.

Ponytail: no network, no exceptions swallowing — the classifier just maps
already-recorded ``SourceResult.status`` into the SOP enum.
"""

from __future__ import annotations

from typing import Literal

from ...schemas_retrieval import (
    CandidateType,
    RetrievalStatus,
    SearchSource,
    SourceResult,
)


# candidate type -> 可用 sources
TYPE_TO_SOURCES: dict[CandidateType, list[SearchSource]] = {
    "paper": ["openalex", "arxiv"],
    "dataset": ["huggingface", "kaggle"],
    "repo": ["github"],
    "project_page": ["openalex"],
    "note": ["manual_fallback"],
}


FailureReason = Literal[
    "source_failed",
    "no_result",
    "query_too_broad",
    "adapter_missing",
    "query_too_narrow",
]


# 已知全部 source, 用于判定 adapter_missing
_KNOWN_SOURCES: set[str] = {
    "openalex", "semantic_scholar", "arxiv", "github",
    "huggingface", "kaggle", "manual_fallback",
}


def expected_sources(candidate_type: CandidateType) -> list[SearchSource]:
    return TYPE_TO_SOURCES.get(candidate_type, [])


def classify_run_result(
    source_results: list[SourceResult],
    candidate_type: CandidateType,
    candidate_count: int,
) -> FailureReason:
    """根据一次 run 的 source_results 推断失败原因.

    约定:
    - candidate_count > 0: 不可能返回 no_result, 返回源里最严重的失败
      (source_failed > adapter_missing > query_too_narrow); 若全部 completed
      则视为 ``query_too_broad`` (还有更窄能拿到更多候选) - 但实际语义上
      此时并不需要重试, 仍可返回 ``query_too_narrow`` 反向提示 (>=0 候选也
      不需要此判断). 因此我们只在 count == 0 时返回 FailureReason, 否则
      退化为 ``query_too_broad`` 表示 "OK, 但可以更精确".

    - candidate_count == 0 且 source_results 为空: 表示 orchestrator 跑完
      没记录任何结果, 按 query_too_narrow 处理 (retry 也许能换 query 命中).
    - candidate_count == 0 且部分 expected sources 未出现: 视作 adapter 缺失.
    """

    expected = expected_sources(candidate_type)
    if not expected:
        return "adapter_missing"

    if candidate_count > 0:
        # 不算失败, 但保留枚举; 下游 gap_report 用 count 决定是否 retry
        return "query_too_broad"

    # candidate_count == 0 时, 按优先级分类
    if not source_results:
        # 完全没记录, retry 可能命中
        return "query_too_narrow"

    any_failed = any(s.status == "failed" for s in source_results)
    any_running = any(s.status == "running" for s in source_results)

    # expected sources 中没有任何 source_results 出现 -> adapter 缺失
    seen_sources = {s.source for s in source_results}
    missing = [s for s in expected if s not in seen_sources]
    if missing and not any_running:
        return "adapter_missing"

    if any_failed and not any_running:
        return "source_failed"

    if any_running:
        # 运行未完成, 但也没有候选, 视作查询过窄 (等待也无济于事的话)
        return "query_too_narrow"

    return "query_too_narrow"


def classify_completion(
    source_results: list[SourceResult],
    candidate_type: CandidateType,
) -> FailureReason:
    """简化版: 只看 source 是否齐全 / 是否 failed, 不依赖 count.

    适用于 orchestrator 已经把所有 expected source 跑完后再调用.
    """

    expected = set(expected_sources(candidate_type))
    seen = {s.source for s in source_results}

    if not expected:
        return "adapter_missing"
    if not seen & expected:
        return "adapter_missing"
    if any(s.status == "failed" for s in source_results if s.source in expected):
        return "source_failed"
    return "query_too_narrow"


if __name__ == "__main__":
    # ponytail: self-check
    from ...schemas_retrieval import SourceResult as _SR

    # 1) 0 候选 + expected 全 failed -> source_failed
    failed = [
        _SR(source="openalex", status="failed", candidate_count=0, error="net"),
        _SR(source="arxiv", status="failed", candidate_count=0, error="net"),
    ]
    r = classify_run_result(failed, "paper", candidate_count=0)
    assert r == "source_failed", f"expected source_failed, got {r}"

    # 2) 0 候选 + 0 queries (empty source_results) -> query_too_narrow
    r = classify_run_result([], "dataset", candidate_count=0)
    assert r == "query_too_narrow", f"expected query_too_narrow, got {r}"

    # 3) >0 候选 -> 返回 source_failed/no_result 以外的值
    ok = [_SR(source="openalex", status="completed", candidate_count=3)]
    r = classify_run_result(ok, "paper", candidate_count=3)
    assert r != "no_result", f"should not be no_result when candidates >0: {r}"

    # 4) classify_completion: 缺 github (repo 应有 github) -> adapter_missing
    no_gh = [_SR(source="huggingface", status="completed", candidate_count=0)]
    r = classify_completion(no_gh, "repo")
    assert r == "adapter_missing", f"expected adapter_missing, got {r}"

    print("OK source_policy self-check passed")