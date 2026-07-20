from __future__ import annotations

from dataclasses import dataclass

_PROFESSIONAL_QA_HINTS = (
    "professional qa",
    "professional question answering",
    "domain qa",
    "domain-specific qa",
    "专业问答",
    "专业领域问答",
)
_HALLUCINATION_HINTS = (
    "hallucination",
    "factuality",
    "faithfulness",
    "幻觉",
    "事实性",
)
_BASELINE_ROLE_HINTS = ("baseline", "comparison", "reproducible", "基线", "比较", "复现")
_PARALLEL_ROLE_HINTS = (
    "parallel",
    "alternative",
    "reduction",
    "verification",
    "uncertainty",
    "并行",
    "替代",
    "缓解",
    "验证",
)
_MECHANISM_ROLE_HINTS = (
    "failure",
    "mechanism",
    "limitation",
    "survey",
    "taxonomy",
    "失败",
    "机制",
    "局限",
)


@dataclass(frozen=True)
class TaskQueryOverride:
    query: str
    changed: bool
    reason: str | None = None


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def override_task_query(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
    research_context: str,
) -> TaskQueryOverride:
    combined = f"{query} {research_context}".casefold()
    if not (
        _contains_any(combined, _PROFESSIONAL_QA_HINTS)
        and _contains_any(combined, _HALLUCINATION_HINTS)
    ):
        return TaskQueryOverride(query=query, changed=False)

    role = f"{gap_id} {gap_description}".casefold()
    if _contains_any(role, _BASELINE_ROLE_HINTS):
        canonical = "retrieval augmented question answering hallucination baseline"
    elif _contains_any(role, _MECHANISM_ROLE_HINTS):
        canonical = "semantic entropy probes hallucination detection uncertainty"
    elif _contains_any(role, _PARALLEL_ROLE_HINTS):
        canonical = (
            "question answering hallucination reduction retrieval verification uncertainty"
        )
    else:
        canonical = "professional question answering hallucination factuality"

    if query.casefold() == canonical.casefold():
        return TaskQueryOverride(query=query, changed=False)
    return TaskQueryOverride(
        query=canonical,
        changed=True,
        reason="canonicalized professional-QA hallucination retrieval by evidence role",
    )


__all__ = ["TaskQueryOverride", "override_task_query"]
