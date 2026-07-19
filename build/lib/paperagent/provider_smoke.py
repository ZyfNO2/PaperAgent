from __future__ import annotations

import asyncio
from dataclasses import dataclass

from paperagent.literature.factory import (
    LiteratureProviderSettings,
    build_literature_runtime,
)
from paperagent.literature.providers import ArxivProvider, OpenAlexProvider
from paperagent.literature.verification import CrossrefVerifier, DataCiteVerifier
from paperagent.schemas.literature import LiteratureFilters, PaperRecord, QueryLane


@dataclass(frozen=True)
class ProviderSmokeSummary:
    openalex: str
    arxiv: str
    crossref: str
    datacite: str

    @property
    def passed(self) -> bool:
        return (
            self.openalex == "success"
            and self.arxiv == "success"
            and self.crossref == "verified"
            and self.datacite == "verified"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "providers": {
                "openalex": self.openalex,
                "arxiv": self.arxiv,
                "crossref": self.crossref,
                "datacite": self.datacite,
            },
        }


async def run_provider_smoke(
    *,
    contact_email: str | None = None,
    timeout_seconds: float = 20.0,
) -> ProviderSmokeSummary:
    settings = LiteratureProviderSettings(
        contact_email=contact_email,
        provider_timeout_seconds=timeout_seconds,
        round_deadline_seconds=max(45.0, timeout_seconds * 2),
    )
    runtime = build_literature_runtime(settings)
    try:
        lane = QueryLane(
            lane_id="release-smoke",
            purpose="baseline",
            query="attention is all you need",
            source_preferences=["openalex", "arxiv"],
            gap_ids=["existence"],
        )
        filters = LiteratureFilters(year_min=2017, year_max=2026)
        openalex = OpenAlexProvider(
            transport=runtime.transport,
            mailto=contact_email,
            timeout_seconds=timeout_seconds,
        )
        arxiv = ArxivProvider(
            transport=runtime.transport,
            timeout_seconds=timeout_seconds,
        )
        openalex_result, arxiv_result = await asyncio.gather(
            openalex.search(lane=lane, filters=filters, limit=3),
            arxiv.search(lane=lane, filters=filters, limit=3),
        )
        crossref = await CrossrefVerifier(
            transport=runtime.transport,
            timeout_seconds=timeout_seconds,
            mailto=contact_email,
        ).verify(
            PaperRecord(
                paper_id="release-smoke-deep-learning",
                canonical_title="Deep learning",
                doi="10.1038/nature14539",
            )
        )
        datacite = await DataCiteVerifier(
            transport=runtime.transport,
            timeout_seconds=timeout_seconds,
        ).verify(
            PaperRecord(
                paper_id="release-smoke-zenodo",
                canonical_title="PaperAgent DataCite release smoke",
                doi="10.5281/zenodo.3723295",
            )
        )
        return ProviderSmokeSummary(
            openalex=openalex_result.status,
            arxiv=arxiv_result.status,
            crossref=crossref.status,
            datacite=datacite.status,
        )
    finally:
        await runtime.aclose()
