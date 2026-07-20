from __future__ import annotations

import math
import re

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.schemas.literature import LiteratureQueryPlan, PaperRecord, RankFeatures

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.lower()))


def _query_text(plan: LiteratureQueryPlan) -> str:
    return " ".join([plan.question, *(lane.query for lane in plan.query_lanes)])


def _paper_text(paper: PaperRecord) -> str:
    return " ".join(filter(None, [paper.canonical_title, paper.abstract or ""]))


def _concept_match(paper: PaperRecord, plan: LiteratureQueryPlan) -> bool:
    return matches_required_candidate_terms(_query_text(plan), _paper_text(paper))


def _relevance(paper: PaperRecord, plan: LiteratureQueryPlan) -> float:
    if not _concept_match(paper, plan):
        return 0.0
    query_tokens = _tokens(_query_text(plan))
    paper_tokens = _tokens(_paper_text(paper))
    if not query_tokens or not paper_tokens:
        return 0.0
    overlap = len(query_tokens & paper_tokens)
    return min(1.0, overlap / max(1, min(len(query_tokens), 8)))


def _gap_coverage(paper: PaperRecord, plan: LiteratureQueryPlan) -> float:
    required = set(plan.required_gap_ids)
    if not required:
        return 1.0
    return len(required & set(paper.matched_gap_ids)) / len(required)


def _metadata_verification(paper: PaperRecord) -> float:
    status_score = {
        "verified": 1.0,
        "pending": 0.65,
        "suspicious": 0.35,
        "failed": 0.0,
        "rejected": 0.0,
    }[paper.verification_status]
    completeness = (
        sum(
            value is not None and value != []
            for value in (
                paper.authors,
                paper.year,
                paper.abstract,
                paper.venue,
                paper.doi or paper.arxiv_id,
            )
        )
        / 5
    )
    return min(1.0, 0.7 * status_score + 0.3 * completeness)


def _recency_fit(paper: PaperRecord, plan: LiteratureQueryPlan, now_year: int) -> float:
    if paper.year is None:
        return 0.25
    filters = plan.filters
    if filters.year_min is not None and paper.year < filters.year_min:
        return 0.0
    if filters.year_max is not None and paper.year > filters.year_max:
        return 0.0
    age = max(0, now_year - paper.year)
    return max(0.2, 1.0 - min(age, 10) / 12)


def _diversity(paper: PaperRecord) -> float:
    providers = {record.provider for record in paper.source_records}
    return min(1.0, 0.5 + 0.25 * max(0, len(providers) - 1))


def rank_papers(
    papers: list[PaperRecord],
    plan: LiteratureQueryPlan,
    *,
    now_year: int,
    final_limit: int = 12,
) -> list[PaperRecord]:
    ranked: list[PaperRecord] = []
    for paper in papers:
        concept_match = _concept_match(paper, plan)
        relevance = _relevance(paper, plan)
        gap_coverage = _gap_coverage(paper, plan)
        metadata = _metadata_verification(paper)
        recency = _recency_fit(paper, plan, now_year)
        diversity = _diversity(paper)
        score = (
            0.40 * relevance
            + 0.25 * gap_coverage
            + 0.15 * metadata
            + 0.10 * recency
            + 0.10 * diversity
        )
        features = RankFeatures(
            relevance=relevance,
            gap_coverage=gap_coverage,
            metadata_verification=metadata,
            recency_fit=recency,
            diversity=diversity,
            citation_tiebreaker=math.log1p(paper.citation_count),
            score=min(1.0, score),
            explanation=[
                f"required_concepts={'matched' if concept_match else 'missing'}",
                f"relevance={relevance:.2f}",
                f"gap_coverage={gap_coverage:.2f}",
                f"verification={paper.verification_status}",
                f"providers={len(paper.source_records)}",
            ],
        )
        ranked.append(paper.model_copy(update={"rank_features": features}))
    ranked.sort(
        key=lambda item: (
            item.rank_features.score if item.rank_features else 0.0,
            item.rank_features.citation_tiebreaker if item.rank_features else 0.0,
            item.paper_id,
        ),
        reverse=True,
    )
    return ranked[:final_limit]
