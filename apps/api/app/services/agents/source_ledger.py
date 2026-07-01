"""SourceLedger — per-call provenance record (Re02 Task 3).

Records every tool call the agent makes so the user can see which adapter
ran which query, what came back, and why. Inspired by ARC
`researchclaw/literature/search.py` `source_stats` and `_literature.py`
`search_meta.json` — we keep the same shape (one row per call) but add a
`target_role` column for the new Re02 role-aware plan.

Output shape (list of dicts):

    {
        "adapter":       "arxiv" | "openalex" | "crossref" | "github",
        "query":         "<verbatim query string>",
        "target_role":   "baseline_or_parallel_paper" | "repo" | "dataset" |
                          "survey" | "broad_recall" | "reference_expansion" |
                          "repo_dataset_followup" | ...,
        "round":         1 | 2 | 3,
        "round_name":    "broad_recall" | "reference_expansion" |
                          "repo_dataset_followup",
        "status":        "ok" | "empty" | "error" | "rate_limited",
        "result_count":  int,
        "error":         str | None,
    }

The ledger is the source of truth for the SourceLedger UI panel — never
derive counts from raw_tool_results alone.

Ponytail: this is a plain dict-list + 4 setters. No ORM, no async, no
network. The agent populates it inline; the test asserts on shape.
"""

from __future__ import annotations

from typing import Any


class SourceLedger:
    """Append-only ledger of every tool call."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        *,
        adapter: str,
        query: str,
        target_role: str,
        round_no: int,
        round_name: str,
        status: str,
        result_count: int,
        error: str | None = None,
    ) -> None:
        """Append one ledger row. Idempotent on schema — only append."""
        self.records.append(
            {
                "adapter": adapter,
                "query": query,
                "target_role": target_role,
                "round": round_no,
                "round_name": round_name,
                "status": status,
                "result_count": result_count,
                "error": error,
            }
        )

    def by_adapter(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for r in self.records:
            out.setdefault(r["adapter"], []).append(r)
        return out

    def by_round(self) -> dict[int, list[dict[str, Any]]]:
        out: dict[int, list[dict[str, Any]]] = {}
        for r in self.records:
            out.setdefault(r["round"], []).append(r)
        return out

    def stats(self) -> dict[str, dict[str, int]]:
        """Aggregate ok/empty/error/rate_limited counts per adapter."""
        out: dict[str, dict[str, int]] = {}
        for r in self.records:
            bucket = out.setdefault(r["adapter"], {"ok": 0, "empty": 0, "error": 0, "rate_limited": 0, "total": 0})
            bucket[r["status"]] = bucket.get(r["status"], 0) + 1
            bucket["total"] += 1
        return out

    def as_list(self) -> list[dict[str, Any]]:
        return list(self.records)
