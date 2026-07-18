from __future__ import annotations

from collections import Counter

from paperagent.schemas.literature import (
    CoverageReport,
    LiteratureQueryPlan,
    PaperRecord,
    RetryRecommendation,
)


def audit_coverage(
    papers: list[PaperRecord],
    plan: LiteratureQueryPlan,
    *,
    round_number: int,
) -> CoverageReport:
    eligible = [paper for paper in papers if paper.verification_status in {"verified", "pending"}]
    gap_coverage: dict[str, int] = {gap_id: 0 for gap_id in plan.required_gap_ids}
    for paper in eligible:
        for gap_id in set(paper.matched_gap_ids) & set(plan.required_gap_ids):
            gap_coverage[gap_id] += 1
    uncovered = [gap_id for gap_id in plan.required_gap_ids if gap_coverage.get(gap_id, 0) == 0]
    providers = {record.provider for paper in papers for record in paper.source_records}
    years = Counter(str(paper.year) if paper.year is not None else "unknown" for paper in papers)
    verification = Counter(paper.verification_status for paper in papers)
    warnings: list[str] = []
    if papers and len(providers) <= 1:
        warnings.append("all results originate from one provider")
    recommendation: RetryRecommendation
    if uncovered and round_number < plan.max_rounds:
        recommendation = "focused_retry"
    elif uncovered:
        recommendation = "budget_exhausted"
    else:
        recommendation = "none"
    return CoverageReport(
        gap_coverage=gap_coverage,
        uncovered_gap_ids=uncovered,
        source_diversity=len(providers),
        publication_year_distribution=dict(sorted(years.items())),
        verification_distribution=dict(sorted(verification.items())),
        retry_recommendation=recommendation,
        warnings=warnings,
    )
