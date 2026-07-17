from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.parse import quote

from paperagent.literature.normalize import canonical_doi, normalized_text
from paperagent.literature.providers.base import AsyncHTTPTransport, HttpxTransport
from paperagent.schemas.literature import PaperRecord

AttemptStatus = Literal["verified", "not_found", "mismatch", "failed"]
_ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})$", re.IGNORECASE)


@dataclass(frozen=True)
class VerificationAttempt:
    status: AttemptStatus
    method: str | None = None
    message: str | None = None


class MetadataVerifier(Protocol):
    async def verify(self, paper: PaperRecord) -> VerificationAttempt: ...


class CrossrefVerifier:
    endpoint = "https://api.crossref.org/works"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
        mailto: str | None = None,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._timeout = timeout_seconds
        self._mailto = mailto

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        if not paper.doi:
            return VerificationAttempt(status="not_found")
        headers = (
            {"User-Agent": f"PaperAgent/0.2 (mailto:{self._mailto})"} if self._mailto else None
        )
        try:
            response = await self._transport.get(
                f"{self.endpoint}/{quote(paper.doi, safe='')}",
                headers=headers,
                timeout=self._timeout,
            )
        except Exception as exc:
            return VerificationAttempt(status="failed", message=str(exc))
        if response.status_code == 404:
            return VerificationAttempt(status="not_found")
        if response.status_code != 200 or not isinstance(response.json_data, dict):
            return VerificationAttempt(status="failed", message=f"HTTP {response.status_code}")
        message = response.json_data.get("message")
        if not isinstance(message, dict):
            return VerificationAttempt(status="failed", message="missing Crossref message")
        found = canonical_doi(str(message.get("DOI") or ""))
        if found != canonical_doi(paper.doi):
            return VerificationAttempt(status="mismatch", message="Crossref DOI mismatch")
        titles = message.get("title")
        if isinstance(titles, list) and titles and isinstance(titles[0], str):
            expected = normalized_text(paper.canonical_title)
            actual = normalized_text(titles[0])
            if expected and actual and expected != actual:
                return VerificationAttempt(status="mismatch", message="Crossref title mismatch")
        return VerificationAttempt(status="verified", method="crossref_doi_exact")


class DataCiteVerifier:
    endpoint = "https://api.datacite.org/dois"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._timeout = timeout_seconds

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        if not paper.doi:
            return VerificationAttempt(status="not_found")
        try:
            response = await self._transport.get(
                f"{self.endpoint}/{quote(paper.doi, safe='')}", timeout=self._timeout
            )
        except Exception as exc:
            return VerificationAttempt(status="failed", message=str(exc))
        if response.status_code == 404:
            return VerificationAttempt(status="not_found")
        if response.status_code != 200 or not isinstance(response.json_data, dict):
            return VerificationAttempt(status="failed", message=f"HTTP {response.status_code}")
        data = response.json_data.get("data")
        if not isinstance(data, dict):
            return VerificationAttempt(status="failed", message="missing DataCite data")
        raw_attributes = data.get("attributes")
        attributes: dict[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
        found = canonical_doi(str(attributes.get("doi") or data.get("id") or ""))
        if found != canonical_doi(paper.doi):
            return VerificationAttempt(status="mismatch", message="DataCite DOI mismatch")
        return VerificationAttempt(status="verified", method="datacite_doi_exact")


class VerificationService:
    def __init__(self, verifiers: list[MetadataVerifier]) -> None:
        self._verifiers = verifiers

    async def verify_all(self, papers: list[PaperRecord]) -> list[PaperRecord]:
        return [await self.verify_one(paper) for paper in papers]

    async def verify_one(self, paper: PaperRecord) -> PaperRecord:
        if paper.doi:
            saw_mismatch = False
            for verifier in self._verifiers:
                attempt = await verifier.verify(paper)
                if attempt.status == "verified":
                    return paper.model_copy(
                        update={
                            "verification_status": "verified",
                            "verification_methods": [attempt.method] if attempt.method else [],
                        }
                    )
                if attempt.status == "mismatch":
                    saw_mismatch = True
            if saw_mismatch:
                return paper.model_copy(update={"verification_status": "suspicious"})
            return paper.model_copy(update={"verification_status": "pending"})
        if paper.arxiv_id:
            if _ARXIV_ID.fullmatch(paper.arxiv_id):
                return paper.model_copy(
                    update={
                        "verification_status": "verified",
                        "verification_methods": ["arxiv_id_syntax"],
                    }
                )
            return paper.model_copy(update={"verification_status": "suspicious"})
        return paper.model_copy(update={"verification_status": "pending"})
