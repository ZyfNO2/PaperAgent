from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from paperagent.literature.adapter import _dataset_relation_names
from paperagent.schemas.literature import PaperRecord


def test_explicit_query_dataset_survives_paper_title_blocklist() -> None:
    papers = (
        cast(
            PaperRecord,
            SimpleNamespace(
                canonical_title="DOTA-Aware Rotated Detector",
                abstract="Compared with the UCAS-AOD dataset.",
            ),
        ),
    )
    names = _dataset_relation_names("DOTA dataset rotated object detection", papers)
    assert names[0] == "DOTA"
    assert "UCAS-AOD" in names


def test_explicit_swat_dataset_is_not_replaced_by_neighbor_mentions() -> None:
    papers = (
        cast(
            PaperRecord,
            SimpleNamespace(
                canonical_title="SWaT Industrial Anomaly Benchmark",
                abstract="Evaluation also references the WADI dataset.",
            ),
        ),
    )
    names = _dataset_relation_names("SWaT dataset anomaly detection", papers)
    assert names[0] == "SWaT"
    assert "WADI" in names
