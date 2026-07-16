from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_json(value: BaseModel | dict[str, Any] | list[Any] | tuple[Any, ...]) -> str:
    if isinstance(value, BaseModel):
        payload: Any = value.model_dump(mode="json", exclude_none=False)
    else:
        payload = value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: BaseModel | dict[str, Any] | list[Any] | tuple[Any, ...]) -> str:
    return sha256_text(canonical_json(value))


def stable_id(prefix: str, *parts: str, length: int = 24) -> str:
    material = "\x1f".join(parts)
    return f"{prefix}_{sha256_text(material)[:length]}"
