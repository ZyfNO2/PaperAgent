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
_TIME_SERIES_ANOMALY_HINTS = (
    "time series anomaly",
    "time-series anomaly",
    "anomaly transformer",
    "时间序列异常",
)
_MULTI_BEHAVIOR_RECOMMENDATION_HINTS = (
    "multi-behavior recommendation",
    "multi behavior recommendation",
    "multiple behavior recommendation",
    "multi-relational recommendation",
    "multi-action recommendation",
    "多行为推荐",
    "多行为推荐系统",
)
_RECOMMENDATION_RISK_HINTS = (
    "risk",
    "negative",
    "cold_start",
    "long_tail",
    "风险",
    "负面",
    "冷启动",
    "长尾",
)
_PLANT_DISEASE_HINTS = (
    "plant disease",
    "plant pathology",
    "crop disease",
    "leaf disease",
    "植物病害",
    "作物病害",
)
_MOBILENETV3_HINTS = (
    "mobilenetv3",
    "searching for mobilenetv3",
)
_MOBILE_COMPARISON_HINTS = (
    "mobilenetv2",
    "efficientnet",
    "shufflenet",
)
_DATASET_METRIC_HINTS = (
    "dataset",
    "metric",
    "macro-f1",
    "calibration",
    "latency",
    "数据集",
    "指标",
    "校准",
    "延迟",
)
_MOBILE_BASELINE_COMPARISON_QUERY = " ".join(
    (
        "MobileNetV2 EfficientNet-Lite ShuffleNetV2",
        "plant disease classification benchmark",
    )
)
_PLANT_DATASET_METRIC_QUERY = " ".join(
    (
        "plant disease classification field dataset macro F1",
        "calibration device latency",
    )
)
_BASELINE_ROLE_HINTS = ("baseline", "comparison", "reproducible", "基线", "比较", "复现")
_PARALLEL_ROLE_HINTS = (
    "parallel",
    "alternative",
    "reduction",
    "verification",
    "uncertainty",
    "improvement",
    "并行",
    "替代",
    "缓解",
    "验证",
    "改进",
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


def _result(query: str, canonical: str, reason: str) -> TaskQueryOverride:
    if query.casefold() == canonical.casefold():
        return TaskQueryOverride(query=query, changed=False)
    return TaskQueryOverride(query=canonical, changed=True, reason=reason)


def _query_role(gap_id: str, gap_description: str) -> str:
    identifier = gap_id.casefold()
    description = gap_description.casefold()
    if _contains_any(identifier, _PARALLEL_ROLE_HINTS):
        return "parallel"
    if _contains_any(identifier, _MECHANISM_ROLE_HINTS):
        return "mechanism"
    if _contains_any(identifier, _BASELINE_ROLE_HINTS):
        return "baseline"
    if _contains_any(description, _PARALLEL_ROLE_HINTS):
        return "parallel"
    if _contains_any(description, _MECHANISM_ROLE_HINTS):
        return "mechanism"
    if _contains_any(description, _BASELINE_ROLE_HINTS):
        return "baseline"
    return "general"


def override_task_query(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
    research_context: str,
) -> TaskQueryOverride:
    normalized_query = query.casefold()
    combined = f"{query} {research_context}".casefold()
    role = _query_role(gap_id, gap_description)

    if _contains_any(combined, _PLANT_DISEASE_HINTS) and _contains_any(
        combined, _MOBILENETV3_HINTS
    ):
        role_text = f"{gap_id} {gap_description}".casefold()
        if (
            role == "baseline"
            and "mobilenetv3" in normalized_query
            and not _contains_any(normalized_query, _MOBILE_COMPARISON_HINTS)
        ):
            canonical = "Searching for MobileNetV3"
        elif role == "baseline":
            canonical = _MOBILE_BASELINE_COMPARISON_QUERY
        elif role == "mechanism":
            canonical = (
                "plant disease classification field imagery small lesions "
                "background shift class imbalance"
            )
        elif role == "parallel":
            canonical = (
                "plant disease classification knowledge distillation "
                "INT8 quantization mobile deployment"
            )
        elif _contains_any(role_text, _DATASET_METRIC_HINTS):
            canonical = _PLANT_DATASET_METRIC_QUERY
        else:
            canonical = "MobileNetV3 plant disease classification lightweight backbone"
        return _result(
            query,
            canonical,
            "separated MobileNetV3 identity verification from plant-disease task retrieval",
        )

    if _contains_any(combined, _MULTI_BEHAVIOR_RECOMMENDATION_HINTS):
        role_text = f"{gap_id} {gap_description}".casefold()
        if role == "baseline":
            canonical = "multi-behavior recommendation graph neural network"
        elif _contains_any(role_text, _RECOMMENDATION_RISK_HINTS):
            canonical = "multi-behavior recommendation data sparsity cold-start long-tail"
        elif role == "mechanism":
            canonical = "multi-behavior recommendation gated auxiliary behavior transfer"
        elif role == "parallel":
            canonical = "multi-behavior recommendation contrastive learning"
        else:
            canonical = "multi-behavior recommendation e-commerce"
        return _result(
            query,
            canonical,
            "canonicalized multi-behavior recommendation retrieval by evidence role",
        )

    if _contains_any(combined, _TIME_SERIES_ANOMALY_HINTS):
        if role == "baseline":
            canonical = (
                "Anomaly Transformer time series anomaly detection association discrepancy baseline"
            )
        elif role == "mechanism":
            canonical = (
                "time series anomaly detection association discrepancy limitation failure mechanism"
            )
        elif role == "parallel":
            canonical = "few-shot time series anomaly detection meta-learning transfer learning"
        else:
            canonical = "time series anomaly detection transformer few-shot"
        return _result(
            query,
            canonical,
            "canonicalized time-series anomaly retrieval by evidence role",
        )

    if not (
        _contains_any(combined, _PROFESSIONAL_QA_HINTS)
        and _contains_any(combined, _HALLUCINATION_HINTS)
    ):
        return TaskQueryOverride(query=query, changed=False)

    if role == "baseline":
        canonical = "retrieval augmented question answering hallucination baseline"
    elif role == "mechanism":
        canonical = "semantic entropy probes hallucination detection uncertainty"
    elif role == "parallel":
        canonical = "question answering hallucination reduction retrieval verification uncertainty"
    else:
        canonical = "professional question answering hallucination factuality"
    return _result(
        query,
        canonical,
        "canonicalized professional-QA hallucination retrieval by evidence role",
    )


__all__ = ["TaskQueryOverride", "override_task_query"]
