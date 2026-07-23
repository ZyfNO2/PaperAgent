from __future__ import annotations

from difflib import SequenceMatcher

from paperagent.literature.normalize import (
    canonical_arxiv_id,
    canonical_doi,
    normalized_author,
    normalized_text,
    stable_paper_id,
)
from paperagent.schemas.literature import (
    MergeWarning,
    PaperRecord,
    ProviderPaper,
    ProviderResult,
    SourceRecord,
)


def _identity_keys(paper: ProviderPaper) -> list[str]:
    doi = canonical_doi(paper.doi)
    arxiv_id = canonical_arxiv_id(paper.arxiv_id)
    keys: list[str] = []
    if doi:
        keys.append(f"doi:{doi}")
    if arxiv_id:
        keys.append(f"arxiv:{arxiv_id}")
    first_author = normalized_author(paper.authors[0] if paper.authors else None)
    if paper.year is not None and first_author:
        keys.append(f"title:{normalized_text(paper.title)}|year:{paper.year}|author:{first_author}")
    return keys


def _approximate_match(left: ProviderPaper, right: PaperRecord) -> bool:
    if left.year is None or right.year is None or abs(left.year - right.year) > 1:
        return False
    left_author = normalized_author(left.authors[0] if left.authors else None)
    right_author = normalized_author(right.authors[0] if right.authors else None)
    if not left_author or left_author != right_author:
        return False
    similarity = SequenceMatcher(
        None,
        normalized_text(left.title),
        normalized_text(right.canonical_title),
    ).ratio()
    return similarity >= 0.94


def _prefer_longer(left: str | None, right: str | None) -> str | None:
    values = [value for value in (left, right) if value]
    return max(values, key=len) if values else None


def _merge_one(
    existing: PaperRecord,
    paper: ProviderPaper,
    result: ProviderResult,
    *,
    approximate: bool,
) -> PaperRecord:
    warnings = list(existing.merge_warnings)
    providers = sorted({record.provider for record in existing.source_records} | {result.provider})
    if existing.year is not None and paper.year is not None and existing.year != paper.year:
        warnings.append(
            MergeWarning(
                code="YEAR_CONFLICT",
                message=f"conflicting publication years: {existing.year} vs {paper.year}",
                providers=providers,
            )
        )
    if existing.authors and paper.authors and existing.authors != paper.authors:
        warnings.append(
            MergeWarning(
                code="AUTHOR_CONFLICT",
                message="provider author lists differ",
                providers=providers,
            )
        )
    if approximate:
        warnings.append(
            MergeWarning(
                code="APPROXIMATE_TITLE_MATCH",
                message="records merged by approximate title, year, and first-author match",
                providers=providers,
            )
        )
    source_records = list(existing.source_records)
    candidate_source = SourceRecord(
        provider=result.provider,
        provider_record_id=paper.provider_record_id,
        request_id=result.request_id,
    )
    if candidate_source not in source_records:
        source_records.append(candidate_source)
    doi = existing.doi or canonical_doi(paper.doi)
    arxiv_id = existing.arxiv_id or canonical_arxiv_id(paper.arxiv_id)
    urls = sorted(set(existing.urls) | set(paper.urls))
    matched_gap_ids = sorted(set(existing.matched_gap_ids) | set(paper.matched_gap_ids))
    authors = (
        existing.authors if len(existing.authors) >= len(paper.authors) else list(paper.authors)
    )
    return existing.model_copy(
        update={
            "canonical_title": _prefer_longer(existing.canonical_title, paper.title),
            "authors": authors,
            "year": existing.year if existing.year is not None else paper.year,
            "abstract": _prefer_longer(existing.abstract, paper.abstract),
            "venue": _prefer_longer(existing.venue, paper.venue),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "openalex_id": existing.openalex_id or paper.openalex_id,
            "semantic_scholar_id": existing.semantic_scholar_id or paper.semantic_scholar_id,
            "urls": urls,
            "source_records": source_records,
            "matched_gap_ids": matched_gap_ids,
            "merge_warnings": warnings,
            "citation_count": max(existing.citation_count, paper.citation_count),
            "publication_type": existing.publication_type or paper.publication_type,
            "language": existing.language or paper.language,
            "verification_status": "suspicious" if approximate else existing.verification_status,
        }
    )


def _new_record(paper: ProviderPaper, result: ProviderResult) -> PaperRecord:
    doi = canonical_doi(paper.doi)
    arxiv_id = canonical_arxiv_id(paper.arxiv_id)
    first_author = paper.authors[0] if paper.authors else ""
    return PaperRecord(
        paper_id=stable_paper_id(
            doi=doi,
            arxiv_id=arxiv_id,
            title=paper.title,
            year=paper.year,
            first_author=first_author,
        ),
        canonical_title=paper.title,
        authors=list(paper.authors),
        year=paper.year,
        abstract=paper.abstract,
        venue=paper.venue,
        doi=doi,
        arxiv_id=arxiv_id,
        openalex_id=paper.openalex_id,
        semantic_scholar_id=paper.semantic_scholar_id,
        urls=sorted(set(paper.urls)),
        source_records=[
            SourceRecord(
                provider=result.provider,
                provider_record_id=paper.provider_record_id,
                request_id=result.request_id,
            )
        ],
        matched_gap_ids=sorted(set(paper.matched_gap_ids)),
        citation_count=paper.citation_count,
        publication_type=paper.publication_type,
        language=paper.language,
    )


def merge_provider_results(
    results: list[ProviderResult],
    *,
    candidate_limit: int = 30,
) -> list[PaperRecord]:
    records: list[PaperRecord] = []
    key_to_index: dict[str, int] = {}
    count = 0
    for result in results:
        if result.status != "success":
            continue
        for paper in result.papers:
            if count >= candidate_limit:
                return records
            count += 1
            keys = _identity_keys(paper)
            match_index = next((key_to_index[key] for key in keys if key in key_to_index), None)
            approximate = False
            if match_index is None:
                for index, existing in enumerate(records):
                    if _approximate_match(paper, existing):
                        match_index = index
                        approximate = True
                        break
            if match_index is None:
                record = _new_record(paper, result)
                records.append(record)
                match_index = len(records) - 1
            else:
                records[match_index] = _merge_one(
                    records[match_index], paper, result, approximate=approximate
                )
            for key in keys:
                key_to_index[key] = match_index
    return records
