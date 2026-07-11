"""Re5.X: Query ledger — append-only record of every search card execution.

Prevents duplicate queries across repair rounds via fingerprint dedup.
Each entry records: round, card_id, fingerprint, source, query, status,
result counts, and diagnosis lineage.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any


def _fingerprint(source: str, query: str) -> str:
    """Normalized fingerprint: source|lowered|stripped|punct_removed query."""
    q = query.strip().lower()
    q = re.sub(r"[^\w\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    raw = f"{source.strip().lower()}|{q}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class QueryLedger:
    """Append-only ledger of search card executions."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._fingerprints: set[str] = set()

    def add(
        self,
        *,
        round: int,
        card_id: str,
        source: str,
        query: str,
        target_role: str = "core",
        source_status: str = "success",
        n_raw: int = 0,
        n_relevant: int = 0,
        n_verified: int = 0,
        diagnosis_parent: str | None = None,
    ) -> dict[str, Any]:
        """Append a new entry. Raises ValueError if fingerprint already exists."""
        fp = _fingerprint(source, query)
        if fp in self._fingerprints:
            raise ValueError(
                f"Duplicate query fingerprint: {source}|{query} "
                f"(matches card_id={self._find_by_fp(fp)})"
            )
        entry = {
            "round": round,
            "card_id": card_id,
            "fingerprint": fp,
            "target_role": target_role,
            "source": source,
            "query": query,
            "source_status": source_status,
            "n_raw": n_raw,
            "n_relevant": n_relevant,
            "n_verified": n_verified,
            "diagnosis_parent": diagnosis_parent,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._entries.append(entry)
        self._fingerprints.add(fp)
        return entry

    def has_fingerprint(self, source: str, query: str) -> bool:
        """Check if a (source, query) pair has already been tried."""
        return _fingerprint(source, query) in self._fingerprints

    def _find_by_fp(self, fp: str) -> str | None:
        for e in self._entries:
            if e["fingerprint"] == fp:
                return e["card_id"]
        return None

    def all_fingerprints(self) -> set[str]:
        return set(self._fingerprints)

    def by_source(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in self._entries:
            out.setdefault(e["source"], []).append(e)
        return out

    def by_role(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in self._entries:
            out.setdefault(e["target_role"], []).append(e)
        return out

    def stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for e in self._entries:
            by_status[e["source_status"]] = by_status.get(e["source_status"], 0) + 1
        return {
            "n_total": len(self._entries),
            "n_unique_fingerprints": len(self._fingerprints),
            "by_status": by_status,
        }

    def as_list(self) -> list[dict[str, Any]]:
        return list(self._entries)
