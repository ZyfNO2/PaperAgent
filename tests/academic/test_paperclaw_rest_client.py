from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from paperagent.academic.contracts import AcademicRetrievalRequest
from paperagent.academic.paperclaw_rest import (
    PaperClawContractError,
    PaperClawRetrievalRESTClient,
    PaperClawTimeoutError,
    PaperClawUpstreamError,
)


def _locator() -> dict[str, Any]:
    return {
        "schema_version": "academic.v1",
        "paper_id": "paper-1",
        "version_id": "version-1",
        "object_id": "paragraph-1",
        "page_number": 1,
        "object_type": "paragraph",
        "source_hash": "a" * 64,
        "section_path": ["Method"],
        "bounding_box": {"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0},
        "paragraph_index": 0,
        "line_range": None,
        "table_row": None,
        "table_column": None,
    }


def _bundle() -> dict[str, Any]:
    return {
        "schema_version": "academic.v1",
        "bundle_id": "bundle-1",
        "project_id": "project-1",
        "query": "dual encoder",
        "candidates": [
            {
                "locator": _locator(),
                "text": "dual encoder evidence",
                "channel_scores": {"lexical": 0.8},
                "fused_score": 0.5,
                "explanation": ["lexical: rank 1"],
                "provenance": "extracted",
            }
        ],
        "sufficiency": "sufficient",
        "reasons": ["grounded"],
        "trace": {
            "trace_id": "trace-1",
            "request_fingerprint": "b" * 64,
            "index_generation_id": "generation-1",
            "channels": ["lexical"],
            "model_fingerprints": {"generation": "test"},
            "rounds_used": {"corrective": 0, "conflict": 0},
            "degraded_channels": [],
            "stop_reason": "budget_or_candidates_exhausted",
        },
    }


def _index_metadata() -> dict[str, str]:
    return {
        "schema_version": "academic.v1",
        "index_version": "academic-object-index.v1",
        "generation_id": "generation-1",
        "corpus_hash": "a" * 64,
        "model_fingerprint": "fixture",
        "content_hash": "b" * 64,
    }


@dataclass
class _Response:
    status_code: int
    payload: Any
    content: bytes = b""

    def json(self) -> Any:
        return self.payload


class _Transport:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any] | None, float]] = []

    def request(self, method, url, *, json=None, timeout=10.0):
        self.calls.append((method, url, json, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _request() -> AcademicRetrievalRequest:
    return AcademicRetrievalRequest(
        project_id="project-1",
        query="dual encoder",
        original_question="How does it work?",
        kind="method",
        round_kind="primary",
        channels=("lexical",),
        paper_ids=("paper-1",),
        object_types=("paragraph",),
    )


def test_rest_client_normalizes_grounded_bundle_without_expanding_budget() -> None:
    bundle = _bundle()
    response = {
        "bundle": bundle,
        "hits": [
            {
                "object": {
                    "schema_version": "academic.v1",
                    "object_id": "paragraph-1",
                    "object_type": "paragraph",
                    "reading_order": 1,
                    "locator": _locator(),
                    "text": "dual encoder evidence",
                    "assets": [],
                    "structured_content": {},
                    "provenance": "extracted",
                },
                "neighbor_context": [],
                "assets": [],
            }
        ],
        "asset_bytes_used": 0,
        "assets_truncated": False,
        "text_chars_used": 21,
        "text_truncated": False,
        "index_metadata": _index_metadata(),
    }
    transport = _Transport([_Response(200, response)])
    client = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=transport,
    )

    result = client.retrieve(_request())

    assert result.trace_id == "trace-1"
    assert result.candidates[0].locator.source_hash == "a" * 64
    sent = transport.calls[0][2]
    assert sent is not None
    assert sent["include_neighbors"] is False
    assert sent["include_assets"] is False


def test_rest_client_fails_closed_on_identity_drift_and_typed_upstream_error() -> None:
    response = {
        "bundle": _bundle(),
        "hits": [],
        "asset_bytes_used": 0,
        "assets_truncated": False,
        "text_chars_used": 21,
        "text_truncated": False,
        "index_metadata": _index_metadata(),
    }
    client = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=_Transport([_Response(200, response)]),
    )
    with pytest.raises(PaperClawContractError, match="grounded hit"):
        client.retrieve(_request())

    upstream = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=_Transport(
            [
                _Response(
                    409,
                    {
                        "detail": {
                            "code": "academic_stale_index",
                            "message": "rebuild",
                        }
                    },
                )
            ]
        ),
    )
    with pytest.raises(PaperClawUpstreamError) as caught:
        upstream.retrieve(_request())
    assert caught.value.upstream_code == "academic_stale_index"


def test_rest_client_distinguishes_healthy_zero_hit_from_contract_failure() -> None:
    zero = _bundle()
    zero["candidates"] = []
    zero["sufficiency"] = "insufficient"
    zero["reasons"] = ["no grounded object matched"]
    client = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=_Transport(
            [
                _Response(
                    200,
                    {
                        "bundle": zero,
                        "hits": [],
                        "asset_bytes_used": 0,
                        "assets_truncated": False,
                        "text_chars_used": 0,
                        "text_truncated": False,
                        "index_metadata": _index_metadata(),
                    },
                )
            ]
        ),
    )
    result = client.retrieve(_request())
    assert result.candidates == ()
    assert result.sufficiency == "insufficient"

    malformed = _bundle()
    malformed["schema_version"] = "academic.v2"
    incompatible = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=_Transport(
            [
                _Response(
                    200,
                    {
                        "bundle": malformed,
                        "hits": [],
                        "asset_bytes_used": 0,
                        "assets_truncated": False,
                        "text_chars_used": 0,
                        "text_truncated": False,
                    },
                )
            ]
        ),
    )
    with pytest.raises(PaperClawContractError):
        incompatible.retrieve(_request())


def test_rest_client_retries_one_timeout_then_surfaces_timeout() -> None:
    transport = _Transport(
        [
            httpx.ReadTimeout("first"),
            httpx.ReadTimeout("second"),
        ]
    )
    client = PaperClawRetrievalRESTClient(
        "https://paperclaw.invalid",
        project_id="project-1",
        transport=transport,
        max_retries=1,
    )

    with pytest.raises(PaperClawTimeoutError):
        client.retrieve(_request())
    assert len(transport.calls) == 2


def test_canonical_rest_fixture_digest_is_frozen() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "academic" / "retrieval_rest_success.v1.json"
    content = fixture.read_bytes()

    assert hashlib.sha256(content).hexdigest() == (
        "34531d0e956f4ca2c99f277ee57f55f945bfae164285a5f21f42f589e57709e1"
    )
    assert b'"schema_version":"academic.v1"' in content
    assert b'"assets_truncated":false' in content

    cases = fixture.with_name("retrieval_rest_cases.v1.json").read_bytes()
    assert hashlib.sha256(cases).hexdigest() == (
        "6266c6d126b6add14a89b82a7f16d6c738b4b47334ce9c1f87dfd625d0591ed2"
    )
    for case in (
        b'"zero_hit"',
        b'"resolve"',
        b'"index"',
        b'"stale_error"',
        b'"integrity_error"',
        b'"asset_budget_truncation"',
        b'"text_budget_truncation"',
        b'"asset_readback"',
    ):
        assert case in cases
