"""Persistent JSON cache for retrieval adapter responses (Re05 SOP §5.3).

Borrowed from AutoResearchClaw ``literature/cache.py``.  Avoids re-hitting
rate-limited sources on every smoke rerun.

Key = ``sha1(adapter + "::" + query)``.  Stored in
``$PAPERAGENT_ADAPTER_CACHE_DIR`` (default ``tmp_re04_eval/adapter_cache``).
TTL = 24h.  Empty results are **never** cached (would poison cache).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Awaitable, Callable


CACHE_DIR = Path(
    os.environ.get("PAPERAGENT_ADAPTER_CACHE_DIR", "tmp_re04_eval/adapter_cache")
)
CACHE_TTL = 24 * 3600  # 24h


def _key(adapter: str, query: str) -> str:
    return hashlib.sha1(f"{adapter}::{query}".encode("utf-8")).hexdigest()


def _enabled() -> bool:
    return os.environ.get("PAPERAGENT_ADAPTER_CACHE", "0") == "1"


def get(adapter: str, query: str) -> list[dict] | None:
    """Return cached list[dict] or None if missing/expired/disabled."""
    if not _enabled():
        return None
    p = CACHE_DIR / f"{_key(adapter, query)}.json"
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > CACHE_TTL:
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return data


def put(adapter: str, query: str, result: list[dict]) -> None:
    """Write successful result to cache. Skip empty (don't cache failures)."""
    if not _enabled():
        return
    if not result:  # critical: don't cache empty
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = CACHE_DIR / f"{_key(adapter, query)}.json"
        p.write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass


async def _cached_adapter(
    adapter: str,
    query: str,
    coro_fn: Callable[[], Awaitable[list[dict]]],
) -> list[dict]:
    """Cache helper: hit -> return cached; miss -> call coro_fn, cache result.

    ``coro_fn`` is a zero-arg async factory (closure capturing any needed
    kwargs).  Returns list[dict]; never raises (caller's coroutine_fn already
    handles its own errors via safe_call or empty-list semantics).
    """
    cached = get(adapter, query)
    if cached is not None:
        return cached
    result = await coro_fn()
    put(adapter, query, result)
    return result