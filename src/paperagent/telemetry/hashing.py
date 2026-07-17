from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from paperagent.telemetry.redaction import redact


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_payload(payload: Any) -> str:
    safe = redact(_jsonable(payload))
    return json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
