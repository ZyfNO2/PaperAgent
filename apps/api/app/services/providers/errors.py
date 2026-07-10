"""Provider error type enumeration for Re6.1 Provider Core.

Typed, structured errors that every provider operation returns instead of
raw exceptions. Each error carries a machine-readable type, human-readable
detail, and optional retry hint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Error type enumeration
# ---------------------------------------------------------------------------

class ProviderErrorType(str, Enum):
    """Machine-readable error categories for provider operations."""

    # Authentication / authorization
    invalid_auth = "invalid_auth"             # 401 — invalid API key or missing credentials
    permission_denied = "permission_denied"   # 403 — key valid but lacks access

    # Resource errors
    model_not_found = "model_not_found"       # 404 — model ID not found on provider

    # Rate / capacity
    rate_limited = "rate_limited"             # 429 — rate limit exceeded

    # Network / transient
    transient_network = "transient_network"   # timeout, 5xx, connection refused

    # Content errors
    context_too_large = "context_too_large"   # 400 / 413 — prompt exceeds token limit
    malformed_output = "malformed_output"     # response is not JSON or fails schema validation
    semantic_contract_fail = "semantic_contract_fail"  # JSON valid but content invalid (e.g. wrong IDs)

    # Protocol / discovery
    unsupported_protocol = "unsupported_protocol"          # unexpected response format
    discovery_unsupported = "discovery_unsupported"        # /v1/models returns 404/405

    # Validation
    url_safety_rejected = "url_safety_rejected"            # SSRF check rejected the URL


# ---------------------------------------------------------------------------
# Typed error dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProviderError:
    """Structured error returned by all provider operations.

    Attributes:
        error_type: Machine-readable error category.
        detail: Human-readable description.
        status_code: Original HTTP status code, if available.
        retryable: Whether the operation can be retried.
        retry_after_s: Suggested retry delay in seconds (only for rate_limited).
        raw_body_snippet: Truncated + redacted response body snippet.
    """
    error_type: ProviderErrorType
    detail: str = ""
    status_code: int | None = None
    retryable: bool = False
    retry_after_s: float | None = None
    raw_body_snippet: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_http_error(status_code: int, body: str = "") -> ProviderError:
    """Classify an HTTP status code into a ProviderError."""
    mapping: dict[int, tuple[ProviderErrorType, str, bool]] = {
        401: (ProviderErrorType.invalid_auth, "invalid API key or credentials", False),
        403: (ProviderErrorType.permission_denied, "access denied", False),
        404: (ProviderErrorType.model_not_found, "model or endpoint not found", False),
        429: (ProviderErrorType.rate_limited, "rate limit exceeded", True),
        500: (ProviderErrorType.transient_network, "internal server error", True),
        502: (ProviderErrorType.transient_network, "bad gateway", True),
        503: (ProviderErrorType.transient_network, "service unavailable", True),
        504: (ProviderErrorType.transient_network, "gateway timeout", True),
    }

    if status_code in mapping:
        etype, detail, retryable = mapping[status_code]
        return ProviderError(
            error_type=etype,
            detail=detail,
            status_code=status_code,
            retryable=retryable,
            raw_body_snippet=body[:200],
        )

    if 400 <= status_code < 500:
        return ProviderError(
            error_type=ProviderErrorType.malformed_output,
            detail=f"client error ({status_code})",
            status_code=status_code,
            retryable=False,
            raw_body_snippet=body[:200],
        )

    if 500 <= status_code < 600:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"server error ({status_code})",
            status_code=status_code,
            retryable=True,
            raw_body_snippet=body[:200],
        )

    return ProviderError(
        error_type=ProviderErrorType.transient_network,
        detail=f"unexpected status {status_code}",
        status_code=status_code,
        retryable=False,
        raw_body_snippet=body[:200],
    )
