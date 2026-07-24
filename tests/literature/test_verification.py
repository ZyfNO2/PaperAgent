from __future__ import annotations

from dataclasses import dataclass

import pytest

from paperagent.literature.providers.base import HTTPResponse
from paperagent.literature.verification import (
    CrossrefVerifier,
    DataCiteVerifier,
    VerificationService,
)
from paperagent.schemas.literature import PaperRecord


@dataclass
class RoutingTransport:
    responses: list[HTTPResponse | Exception]

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def paper(**updates: object) -> PaperRecord:
    values: dict[str, object] = {
        "paper_id": "paper-1",
        "canonical_title": "Reliable Retrieval",
        "authors": ["Jane Doe"],
        "year": 2024,
        "doi": "10.1000/abc",
        "matched_gap_ids": ["g1"],
    }
    values.update(updates)
    return PaperRecord(**values)


@pytest.mark.asyncio
async def test_crossref_exact_doi_verifies_paper() -> None:
    transport = RoutingTransport(
        [
            HTTPResponse(
                status_code=200,
                headers={},
                json_data={
                    "message": {
                        "DOI": "10.1000/ABC",
                        "title": ["Reliable Retrieval"],
                        "author": [{"given": "Jane", "family": "Doe"}],
                    }
                },
                text="",
            )
        ]
    )
    verified = await VerificationService([CrossrefVerifier(transport=transport)]).verify_all(
        [paper()]
    )
    assert verified[0].verification_status == "verified"
    assert verified[0].verification_methods == ["crossref_doi_exact"]


@pytest.mark.asyncio
async def test_datacite_fallback_verifies_when_crossref_not_found() -> None:
    transport = RoutingTransport(
        [
            HTTPResponse(status_code=404, headers={}, json_data={}, text=""),
            HTTPResponse(
                status_code=200,
                headers={},
                json_data={"data": {"id": "10.1000/abc", "attributes": {"doi": "10.1000/abc"}}},
                text="",
            ),
        ]
    )
    service = VerificationService(
        [CrossrefVerifier(transport=transport), DataCiteVerifier(transport=transport)]
    )
    verified = await service.verify_all([paper()])
    assert verified[0].verification_status == "verified"
    assert verified[0].verification_methods == ["datacite_doi_exact"]


@pytest.mark.asyncio
async def test_arxiv_identifier_can_be_verified_without_doi_network() -> None:
    verified = await VerificationService([]).verify_all([paper(doi=None, arxiv_id="2401.12345")])
    assert verified[0].verification_status == "verified"
    assert verified[0].verification_methods == ["arxiv_id_syntax"]


@pytest.mark.asyncio
async def test_transport_failure_stays_pending_not_verified() -> None:
    verifier = CrossrefVerifier(transport=RoutingTransport([TimeoutError("slow")]))
    verified = await VerificationService([verifier]).verify_all([paper()])
    assert verified[0].verification_status == "pending"
    assert verified[0].verification_methods == []


@pytest.mark.asyncio
async def test_invalid_identifier_is_rejected() -> None:
    verified = await VerificationService([]).verify_all(
        [paper(doi=None, arxiv_id="not-an-arxiv-id")]
    )
    assert verified[0].verification_status == "suspicious"
