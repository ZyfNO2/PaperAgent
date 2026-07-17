from __future__ import annotations

from typing import Any

from paperagent.telemetry.hashing import canonical_payload, hash_payload
from paperagent.telemetry.redaction import redact


def make_event(*args: Any, **kwargs: Any) -> Any:
    from paperagent.telemetry.events import make_event as _make_event

    return _make_event(*args, **kwargs)


__all__ = ["canonical_payload", "hash_payload", "make_event", "redact"]
