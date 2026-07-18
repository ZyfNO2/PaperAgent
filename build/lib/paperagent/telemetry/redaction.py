from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)([?&](?:api[_-]?key|apikey|token|access[_-]?token|refresh[_-]?token|secret|password)=)[^&#\s]+"
)
_ASSIGNMENT_SECRET_PATTERN = re.compile(
    r"(?i)\b([A-Za-z0-9_-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret))"
    r"\s*([:=])\s*([^\s,;]+)"
)


def _is_secret_key(value: object) -> bool:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in _SECRET_KEYS:
        return True
    return (
        normalized.endswith("_api_key")
        or normalized.endswith("_access_token")
        or normalized.endswith("_refresh_token")
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.startswith("authorization_")
    )


def _redact_string(value: str) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    redacted = _QUERY_SECRET_PATTERN.sub(r"\1[REDACTED]", redacted)
    return _ASSIGNMENT_SECRET_PATTERN.sub(r"\1\2[REDACTED]", redacted)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_secret_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value
