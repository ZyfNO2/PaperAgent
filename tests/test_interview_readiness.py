from __future__ import annotations

from pathlib import Path

from paperagent.gold_case import run_gold_case
from paperagent.interview_readiness import render_interview_readiness


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_interview_readiness_binds_evidence_and_limitations() -> None:
    report = run_gold_case(REPOSITORY_ROOT)
    rendered = render_interview_readiness(report)

    assert report.report_digest in rendered
    assert "Scientific acceptance: **NOT CLAIMED**" in rendered
    assert "Recall@5: `1.000`" in rendered
    assert "Unsupported claim rate: `0.000`" in rendered
    assert "not real scientific validation" in rendered
    assert "A+B+C" in rendered
