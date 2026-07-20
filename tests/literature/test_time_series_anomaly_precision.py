from __future__ import annotations

import pytest

from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.literature.task_query_overrides import override_task_query


@pytest.mark.parametrize(
    ("query", "candidate", "expected"),
    [
        (
            "Anomaly Transformer time series anomaly detection association discrepancy baseline",
            "Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy "
            "introduces an unsupervised anomaly detector for multivariate time series.",
            True,
        ),
        (
            "time series anomaly detection association discrepancy limitation failure mechanism",
            "A survey of multivariate time-series anomaly detection studies temporal dependency, "
            "distribution shift, anomaly detection failures, and transformer limitations.",
            True,
        ),
        (
            "few-shot time series anomaly detection meta-learning transfer learning",
            "Few-shot anomaly detection for industrial time series uses meta-learning with few "
            "labeled examples and transfer learning across sensor data streams.",
            True,
        ),
        (
            "few-shot time series anomaly detection meta-learning transfer learning",
            "Anomaly Detection in Human Language via Meta-Learning: A Few-Shot Approach.",
            False,
        ),
        (
            "few-shot time series anomaly detection meta-learning transfer learning",
            "The solution for a few-shot object detection challenge uses a transformer detector.",
            False,
        ),
        (
            "time series anomaly detection association discrepancy limitation failure mechanism",
            "Unsupervised brain imaging 3D anomaly detection with transformer reconstruction.",
            False,
        ),
        (
            "time series anomaly detection association discrepancy limitation failure mechanism",
            "A review of transformer models for plant disease anomaly recognition in leaf images.",
            False,
        ),
        (
            "Anomaly Transformer time series anomaly detection association discrepancy baseline",
            "A generic transformer performs anomaly detection on temporal medical images.",
            False,
        ),
    ],
)
def test_time_series_anomaly_candidate_guard(query: str, candidate: str, expected: bool) -> None:
    assert matches_specialized_candidate_terms(query, candidate) is expected


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_reproducibility",
            "Anomaly Transformer baseline reproducibility and comparison evidence",
            "Anomaly Transformer time series anomaly detection association discrepancy baseline",
        ),
        (
            "mechanism_and_limitations",
            "time-series anomaly failure mechanism and limitations",
            "time series anomaly detection association discrepancy limitation failure mechanism",
        ),
        (
            "parallel_methods_and_improvements",
            "parallel few-shot methods compared with the Anomaly Transformer baseline",
            "few-shot time series anomaly detection meta-learning transfer learning",
        ),
    ],
)
def test_time_series_anomaly_queries_are_role_specific(
    gap_id: str, description: str, expected: str
) -> None:
    result = override_task_query(
        "generic anomaly transformer query",
        gap_id=gap_id,
        gap_description=description,
        research_context="小样本时间序列异常检测, 以 Anomaly Transformer 为基线",
    )

    assert result.changed is True
    assert result.query == expected
