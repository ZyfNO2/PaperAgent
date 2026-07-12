"""HuggingFace dataset 检索 (SOP §8.5).

Re05 §2.2: returned dicts are normalized so downstream
``collect_papers_from_raw`` (or any unified raw-pool consumer) can
treat HF rows as dataset-shaped evidence:

  - ``title``   = HF dataset id (falls back to "" if missing)
  - ``evidence_type`` = "dataset"
  - ``source`` = "huggingface"
  - ``tags``  = cardData.task_categories merged with top-level tags
  - extra fields (likes/downloads/lastModified/cardData) preserved
    for ER to inspect.

We also expand from ``queries[:1]`` to ``queries[:2]`` so the adapter
actually queries more than one term per round.
"""

from __future__ import annotations

from typing import Any

from .._http import HttpError, fetch_with_timeout

from apps.api.app.services.network_guard import NetworkPolicyGuard


HF_API = "https://huggingface.co/api/datasets"

# Per-query slice size (was 1; SOP §2.2 raises to 2).
HF_QUERIES_PER_ROUND = 2


def _row_to_dataset_dict(r: dict[str, Any]) -> dict[str, Any]:
    """Normalize one HF API row into a dataset-shaped dict."""
    title = str(r.get("id") or r.get("name") or "").strip()
    card = r.get("cardData") or {}
    tasks = card.get("task_categories") if isinstance(card, dict) else None
    top_tags = r.get("tags") if isinstance(r.get("tags"), list) else []
    tags = list(top_tags)
    if isinstance(tasks, list):
        for t in tasks:
            if isinstance(t, str) and t not in tags:
                tags.append(t)
    out = {
        "title": title,
        "evidence_type": "dataset",
        "source": "huggingface",
        "url": f"https://huggingface.co/datasets/{title}" if title else None,
        "tags": tags,
        "name": title,
    }
    # Preserve optional HF metadata for downstream consumers / ER.
    for k in ("id", "likes", "downloads", "lastModified",
              "cardData", "private", "gated"):
        if k in r:
            out.setdefault(k, r[k])
    return out


async def huggingface_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """从 HuggingFace datasets API 检索.

    Returns dataset-normalized rows (``title=id``,
    ``evidence_type="dataset"``, ``source="huggingface"``).
    """
    NetworkPolicyGuard.assert_online("huggingface")
    results: list[dict] = []
    qs = list(queries[:HF_QUERIES_PER_ROUND]) if queries else []
    seen_ids: set[str] = set()
    for q in qs:
        url = f"{HF_API}?search={q}&limit={top_k}"
        try:
            data = await fetch_with_timeout(url, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, list):
            continue
        for r in data:
            if isinstance(r, dict):
                row = _row_to_dataset_dict(r)
                if not row.get("title") or row["title"] in seen_ids:
                    continue
                seen_ids.add(row["title"])
                results.append(row)
                if len(results) >= top_k:
                    return results
    return results[:top_k]
