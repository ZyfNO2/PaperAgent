"""Narrow fail-closed client for PaperClaw's Academic Retrieval REST seam."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any, Protocol, cast

import httpx

from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicLocator,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
)
from paperagent.academic.paperclaw_adapter import normalize_bundle_payload


class PaperClawRESTError(RuntimeError):
    code = "paperclaw_transport_failure"
    retryable = False

    def __init__(self, message: str, *, upstream_code: str | None = None) -> None:
        super().__init__(message)
        self.upstream_code = upstream_code


class PaperClawTimeoutError(PaperClawRESTError):
    code = "paperclaw_timeout"
    retryable = True


class PaperClawTransportError(PaperClawRESTError):
    retryable = True


class PaperClawMalformedResponseError(PaperClawRESTError):
    code = "paperclaw_malformed_response"


class PaperClawContractError(PaperClawRESTError):
    code = "paperclaw_contract_incompatible"


class PaperClawUpstreamError(PaperClawRESTError):
    code = "paperclaw_upstream_failure"


class _Response(Protocol):
    status_code: int
    content: bytes

    def json(self) -> Any: ...


class SyncHTTPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> _Response: ...


class HttpxSyncTransport:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(follow_redirects=False)

    def request(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        return self._client.request(method, url, json=json, timeout=timeout)

    def close(self) -> None:
        self._client.close()


_KNOWN_UPSTREAM_CODES = {
    "academic_index_not_ready",
    "academic_locator_not_found",
    "academic_stale_schema",
    "academic_stale_index",
    "academic_fingerprint_mismatch",
    "academic_integrity_failure",
    "academic_invalid_budget",
    "paper_not_found",
}


class PaperClawRetrievalRESTClient:
    """Validate transport, wire identity and hashes without reimplementing search."""

    def __init__(
        self,
        base_url: str,
        *,
        project_id: str,
        transport: SyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("PaperClaw base URL must use http or https")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("PaperClaw timeout must be in (0, 60]")
        if not 0 <= max_retries <= 1:
            raise ValueError("PaperClaw retries must be in [0, 1]")
        self._base_url = base_url.rstrip("/")
        if not project_id:
            raise ValueError("PaperClaw project_id is required")
        self._project_id = project_id
        self._transport = cast(
            SyncHTTPTransport, transport if transport is not None else HttpxSyncTransport()
        )
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult:
        if request.project_id != self._project_id:
            raise PaperClawContractError(
                "retrieval request project does not match configured PaperClaw project"
            )
        payload = {
            "query": request.query,
            "channels": list(request.channels),
            "paper_ids": list(request.paper_ids),
            "object_types": list(request.object_types),
            "section_scope": list(request.section_scope),
            "max_candidates": request.max_candidates,
            "max_chars": request.max_chars,
            "include_neighbors": False,
            "neighbor_count": 0,
            "include_assets": False,
            "max_asset_bytes": 1,
        }
        raw = self._json_request(
            "POST",
            f"/v1/projects/{request.project_id}/academic/search",
            payload,
        )
        bundle = raw.get("bundle")
        hits = raw.get("hits")
        if not isinstance(bundle, Mapping) or not isinstance(hits, list):
            raise PaperClawMalformedResponseError("PaperClaw search response is malformed")
        if bundle.get("project_id") != request.project_id:
            raise PaperClawContractError("PaperClaw bundle project identity drifted")
        try:
            normalized = normalize_bundle_payload(bundle)
        except ValueError as exc:
            raise PaperClawContractError("PaperClaw EvidenceBundle is incompatible") from exc
        metadata = raw.get("index_metadata")
        trace = bundle.get("trace")
        if not isinstance(metadata, Mapping):
            raise PaperClawMalformedResponseError("PaperClaw index metadata is missing")
        if not isinstance(trace, Mapping):
            raise PaperClawMalformedResponseError("PaperClaw retrieval trace is missing")
        if (
            metadata.get("schema_version") != "academic.v1"
            or metadata.get("index_version") != "academic-object-index.v1"
            or metadata.get("generation_id") != trace.get("index_generation_id")
        ):
            raise PaperClawContractError("PaperClaw index metadata is incompatible")
        hit_identities = {
            self._object_identity(hit.get("object")) for hit in hits if isinstance(hit, Mapping)
        }
        for candidate in normalized.candidates:
            identity = (
                candidate.locator.paper_id,
                candidate.locator.version_id,
                candidate.locator.source_hash,
                candidate.locator.object_id,
                candidate.locator.object_type,
                candidate.locator.page_number,
            )
            if identity not in hit_identities:
                raise PaperClawContractError("PaperClaw candidate has no matching grounded hit")
        if raw.get("assets_truncated") not in {True, False}:
            raise PaperClawMalformedResponseError("PaperClaw asset truncation state is malformed")
        if raw.get("text_truncated") not in {True, False} or not isinstance(
            raw.get("text_chars_used"), int
        ):
            raise PaperClawMalformedResponseError("PaperClaw text budget state is malformed")
        return normalized.model_copy(update={"trace_details": dict(trace)})

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        raw = self._json_request(
            "POST",
            f"/v1/projects/{self._project_id}/academic/resolve",
            {"locator": self._locator_wire(locator)},
        )
        raw_locator = raw.get("locator")
        if not isinstance(raw_locator, Mapping):
            raise PaperClawMalformedResponseError("PaperClaw resolved object has no locator")
        normalized = self._locator(raw_locator)
        if normalized != locator:
            raise PaperClawContractError("PaperClaw resolved a different locator")
        provenance = raw.get("provenance")
        if provenance not in {"extracted", "inferred"}:
            raise PaperClawMalformedResponseError("PaperClaw resolved provenance is malformed")
        return AcademicCandidate(
            evidence_id=(f"{locator.paper_id}:{locator.version_id}:{locator.object_id}"),
            locator=locator,
            text=str(raw.get("text") or ""),
            score=1.0,
            provenance=provenance,
            explanation=("paperclaw_rest_resolve",),
        )

    def read_asset(self, project_id: str, locator: AcademicLocator, asset_hash: str) -> bytes:
        if re.fullmatch(r"[0-9a-f]{64}", asset_hash) is None:
            raise ValueError("asset_hash must be a SHA-256")
        response = self._request(
            "POST",
            f"/v1/projects/{project_id}/academic/asset",
            {"locator": self._locator_wire(locator), "asset_hash": asset_hash},
        )
        if hashlib.sha256(response.content).hexdigest() != asset_hash:
            raise PaperClawContractError("PaperClaw asset hash mismatch")
        return response.content

    def _json_request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        response = self._request(method, path, payload)
        try:
            value = response.json()
        except Exception as exc:
            raise PaperClawMalformedResponseError("PaperClaw response is not valid JSON") from exc
        if not isinstance(value, Mapping):
            raise PaperClawMalformedResponseError("PaperClaw response must be a JSON object")
        return value

    def _request(self, method: str, path: str, payload: Mapping[str, Any]) -> _Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport.request(
                    method,
                    f"{self._base_url}{path}",
                    json=payload,
                    timeout=self._timeout,
                )
            except (httpx.TimeoutException, TimeoutError) as exc:
                if attempt < self._max_retries:
                    continue
                raise PaperClawTimeoutError("PaperClaw request timed out") from exc
            except (httpx.TransportError, OSError) as exc:
                if attempt < self._max_retries:
                    continue
                raise PaperClawTransportError("PaperClaw transport failed") from exc
            if 200 <= response.status_code < 300:
                return response
            self._raise_upstream(response)
        raise AssertionError("unreachable")

    @staticmethod
    def _raise_upstream(response: _Response) -> None:
        try:
            payload = response.json()
            detail = payload.get("detail", {}) if isinstance(payload, Mapping) else {}
            code = detail.get("code") if isinstance(detail, Mapping) else None
        except Exception:
            code = None
        if code not in _KNOWN_UPSTREAM_CODES:
            raise PaperClawUpstreamError(
                f"PaperClaw returned HTTP {response.status_code}",
                upstream_code=str(code) if code is not None else None,
            )
        raise PaperClawUpstreamError(
            f"PaperClaw rejected the request: {code}",
            upstream_code=str(code),
        )

    @staticmethod
    def _locator(raw: Mapping[str, Any]) -> AcademicLocator:
        payload = dict(raw)
        bbox = payload.get("bounding_box")
        if isinstance(bbox, Mapping):
            payload["bounding_box"] = (
                bbox["x0"],
                bbox["y0"],
                bbox["x1"],
                bbox["y1"],
            )
        try:
            return AcademicLocator.model_validate(payload)
        except Exception as exc:
            raise PaperClawContractError("PaperClaw locator is incompatible") from exc

    @staticmethod
    def _locator_wire(locator: AcademicLocator) -> dict[str, Any]:
        payload = locator.model_dump(mode="json")
        if locator.bounding_box is not None:
            x0, y0, x1, y1 = locator.bounding_box
            payload["bounding_box"] = {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            }
        return payload

    @classmethod
    def _object_identity(cls, raw: Any) -> tuple[str, str, str, str, str, int] | None:
        if not isinstance(raw, Mapping):
            return None
        locator = raw.get("locator")
        if not isinstance(locator, Mapping):
            return None
        normalized = cls._locator(locator)
        if raw.get("object_id") != normalized.object_id:
            raise PaperClawContractError("PaperClaw object identity drifted")
        if (
            raw.get("object_type") != normalized.object_type
            or raw.get("locator", {}).get("page_number") != normalized.page_number
        ):
            raise PaperClawContractError("PaperClaw object locator identity drifted")
        assets = raw.get("assets")
        if not isinstance(assets, list) or any(
            not isinstance(asset, Mapping)
            or re.fullmatch(r"[0-9a-f]{64}", str(asset.get("asset_hash", ""))) is None
            for asset in assets
        ):
            raise PaperClawContractError("PaperClaw object asset identity is malformed")
        return (
            normalized.paper_id,
            normalized.version_id,
            normalized.source_hash,
            normalized.object_id,
            normalized.object_type,
            normalized.page_number,
        )
