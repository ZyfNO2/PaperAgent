"""Session 61 M6: RetrievalRetryPlanner.

Given a ``GapReport`` and the raw topic, produce a single-shot retry plan.
If any gap is recoverable (no_paper / no_dataset / no_repo NOT caused by
``source_failed`` / ``adapter_missing``), ``should_retry=True``.

Ponytail: 1 round max. No recursion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...schemas_retrieval import CandidateType
from .gap_report import GapItem, GapReport


@dataclass
class RetryPlan:
    should_retry: bool = False
    extra_queries_by_type: dict[CandidateType, list[str]] = field(default_factory=dict)
    reason: str = ""


# 各缺口 -> 补搜 query 模板
_EXTRA_TEMPLATES: dict[str, list[str]] = {
    "no_dataset": [
        "{topic} crack detection dataset",
        "{topic} structural health monitoring dataset",
        "{topic} benchmark public HuggingFace",
    ],
    "no_repo": [
        "{topic} 3D reconstruction github pytorch",
        "{topic} baseline code implementation",
        "{topic} train github",
    ],
    "no_paper": [
        "{topic} survey",
        "{topic} benchmark review",
    ],
}

# 这些原因 retry 也救不了
_NON_RETRYABLE = {"source_failed", "adapter_missing"}


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = (it or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def plan_retry(gap_report: GapReport, raw_topic: str) -> RetryPlan:
    raw = (raw_topic or "").strip() or "本课题"

    non_retryable = {
        g.category for g in gap_report.gaps if g.category in _NON_RETRYABLE
    }

    # 找出每一类缺口对应的 category (no_*)
    extra: dict[CandidateType, list[str]] = {}
    categories_seen = {g.category for g in gap_report.gaps}

    if "no_dataset" in categories_seen and "source_failed" not in non_retryable and "adapter_missing" not in non_retryable:
        extra["dataset"] = _dedup_keep_order(
            t.replace("{topic}", raw) for t in _EXTRA_TEMPLATES["no_dataset"]
        )

    if "no_repo" in categories_seen and "source_failed" not in non_retryable and "adapter_missing" not in non_retryable:
        extra["repo"] = _dedup_keep_order(
            t.replace("{topic}", raw) for t in _EXTRA_TEMPLATES["no_repo"]
        )

    if "no_paper" in categories_seen and "source_failed" not in non_retryable and "adapter_missing" not in non_retryable:
        extra["paper"] = _dedup_keep_order(
            t.replace("{topic}", raw) for t in _EXTRA_TEMPLATES["no_paper"]
        )

    should_retry = bool(extra)

    if non_retryable and not extra:
        reason = (
            f"缺口全部由 {'/'.join(sorted(non_retryable))} 引起, "
            "retry 无法修复, 跳过。"
        )
    elif extra:
        kinds = "/".join(sorted(extra.keys()))
        reason = f"对 {kinds} 类型生成补搜 query, 准备一轮 retry。"
    else:
        reason = "无缺口, 不需要 retry。"

    return RetryPlan(
        should_retry=should_retry,
        extra_queries_by_type=extra,
        reason=reason,
    )


if __name__ == "__main__":
    # ponytail: self-check
    # 1) gap with no_dataset + no_repo -> should_retry True, 两个 list 非空
    g1 = GapReport(
        gaps=[
            GapItem(category="no_dataset", details="x"),
            GapItem(category="no_repo", details="y"),
        ],
    )
    p1 = plan_retry(g1, "三维成像损伤检测")
    assert p1.should_retry, p1
    assert p1.extra_queries_by_type.get("dataset"), p1.extra_queries_by_type
    assert p1.extra_queries_by_type.get("repo"), p1.extra_queries_by_type
    assert all("三维成像损伤检测" in q for q in p1.extra_queries_by_type["dataset"])
    assert all("三维成像损伤检测" in q for q in p1.extra_queries_by_type["repo"])

    # 2) all source_failed -> should_retry False
    g2 = GapReport(
        gaps=[
            GapItem(category="source_failed", details="x"),
            GapItem(category="no_paper", details="y"),
        ],
    )
    p2 = plan_retry(g2, "topic")
    assert not p2.should_retry, p2

    print("OK retry_planner self-check passed")