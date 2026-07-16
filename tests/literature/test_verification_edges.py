from __future__ import annotations

from dataclasses import dataclass

import pytest

from paperagent.literature.providers.base import HTTPResponse
from paperagent.literature.verification import (
    CrossrefVerifier,
    DataCiteVerifier,
    VerificationAttempt,
    VerificationService,
)
from paperagent.schemas.literature import PaperRecord


@dataclass
class QueueTransport:
    responses: list[HTTPResponse | Exception]

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        del url, params, headers, timeout
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StaticVerifier:
    def __init__(self, attempt: VerificationAttempt) -> None:
        self.attempt = attempt

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        del paper
        return self.attempt


def paper(**updates: object) -> PaperRecord:
    values: dict[str, object] = {
        "paper_id": "p1",
        "canonical_title": "Reliable Retrieval",
        "authors": ["Jane Doe"],
        "year": 2024,
        "doi": "10.1000/abc",
    }
    values.update(updates)
    return PaperRecord(**values)


@pytest.mark.asyncio
async def test_crossref_without_doi_is_not_found() -> None:
    attempt = await CrossrefVerifier(transport=QueueTransport([])).verify(paper(doi=None))
    assert attempt.status == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "status"),
    [
        (HTTPResponse(404, {}, {}, ""), "not_found"),
        (HTTPResponse(500, {}, {}, ""), "failed"),
        (HTTPResponse(200, {}, {"message": "bad"}, ""), "failed"),
        (
            HTTPResponse(
                200,
                {},
                {"message": {"DOI": "10.1000/other", "title": ["Reliable Retrieval"]}},
                "",
            ),
            "mismatch",
        ),
        (
            HTTPResponse(
                200,
                {},
                {"message": {"DOI": "10.1000/abc", "title": ["Different Title"]}},
                "",
            ),
            "mismatch",
        ),
    ],
)
async def test_crossref_non_success_paths(response: HTTPResponse, status: str) -> None:
    attempt = await CrossrefVerifier(transport=QueueTransport([response])).verify(paper())
    assert attempt.status == status


@pytest.mark.asyncio
async def test_crossref_transport_error_is_failed() -> None:
    attempt = await CrossrefVerifier(transport=QueueTransport([RuntimeError("network")])).verify(
        paper()
    )
    assert attempt.status == "failed"


@pytest.mark.asyncio
async def test_datacite_without_doi_is_not_found() -> None:
    attempt = await DataCiteVerifier(transport=QueueTransport([])).verify(paper(doi=None))
    assert attempt.status == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "status"),
    [
        (HTTPResponse(404, {}, {}, ""), "not_found"),
        (HTTPResponse(500, {}, {}, ""), "failed"),
        (HTTPResponse(200, {}, {"data": "bad"}, ""), "failed"),
        (
            HTTPResponse(
                200,
                {},
                {"data": {"id": "10.1000/other", "attributes": {}}},
                "",
            ),
            "mismatch",
        ),
    ],
)
async def test_datacite_non_success_paths(response: HTTPResponse, status: str) -> None:
    attempt = await DataCiteVerifier(transport=QueueTransport([response])).verify(paper())
    assert attempt.status == status


@pytest.mark.asyncio
async def test_datacite_transport_error_is_failed() -> None:
    attempt = await DataCiteVerifier(transport=QueueTransport([RuntimeError("network")])).verify(
        paper()
    )
    assert attempt.status == "failed"


@pytest.mark.asyncio
async def test_verification_service_marks_mismatch_suspicious() -> None:
    service = VerificationService([StaticVerifier(VerificationAttempt(status="mismatch"))])
    result = await service.verify_one(paper())
    assert result.verification_status == "suspicious"


@pytest.mark.asyncio
async def test_verification_service_leaves_unidentified_paper_pending() -> None:
    result = await VerificationService([]).verify_one(paper(doi=None, arxiv_id=None))
    assert result.verification_status == "pending"


@pytest.mark.asyncio
async def test_failed_verifier_does_not_turn_into_verified() -> None:
    service = VerificationService([StaticVerifier(VerificationAttempt(status="failed"))])
    result = await service.verify_one(paper())
    assert result.verification_status == "pending"
