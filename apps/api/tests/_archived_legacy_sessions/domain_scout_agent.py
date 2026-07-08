"""Re10 DomainScoutAgent — SOP §3.2 + §10.1.

LLM-only (no network call) scouting agent. Produces a domain keyword
matrix + ``must_search`` / ``avoid_search`` lists the SearchPlanner
consumes in round 1.

The agent never judges the topic, never builds a final candidate pool,
never collapses to a single domain. It returns a *flat* JSON shape
whose keys are fixed by the SOP so the loop can read it without
branching.

ponytail:
- Single LLM call, capped at 1500 tokens (SOP §10.1).
- All-network-free: DomainScout just looks at topic + topic_atoms + a
  history of previous successes/noise.  Network probes belong in
  SearchExecutor.
- Offline fallback derives ``must_search`` from topic_atoms only — never
  fabricates dataset/repo names.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strict JSON shape expected by SearchReflectionLoop.  Every key is
# present even when empty, so the caller never has to .get() defensively.
# ---------------------------------------------------------------------------

_EMPTY_DOMAIN_KEYWORDS = {
    "zh": [], "en": [], "method": [], "object": [], "task": [],
    "scenario": [], "dataset_terms": [], "baseline_terms": [], "repo_terms": [],
}


def _empty_payload(search_notes: str = "") -> dict:
    return {
        "domain_keywords": copy.deepcopy(_EMPTY_DOMAIN_KEYWORDS),
        "must_search": [],
        "avoid_search": [],
        "known_baseline_families": [],
        "known_dataset_families": [],
        "search_notes": search_notes,
    }


# ---------------------------------------------------------------------------
# Offline fallback (SOP §3.2): when LLM fails OR atoms are empty, derive
# ``must_search`` deterministically from topic_atoms.
# ---------------------------------------------------------------------------


def _first_en_atom(topic_atoms: dict, axis: str) -> str:
    atoms = topic_atoms.get(axis) or []
    for a in atoms:
        if isinstance(a, dict):
            v = a.get("en") or a.get("zh")
            if v:
                return str(v).strip()
        elif isinstance(a, str) and a.strip():
            return a.strip()
    return ""


def _offline_must_search(topic_atoms: dict) -> list[str]:
    out: list[str] = []
    for axis in ("task", "object"):
        atom_en = _first_en_atom(topic_atoms, axis)
        if not atom_en:
            continue
        # Suffix per axis — task→benchmark, object→benchmark; both are
        # the user's most useful search probes.
        out.append(f"{atom_en} {axis} benchmark")
    # Dedup while preserving order.
    seen: set[str] = set()
    dedup: list[str] = []
    for q in out:
        if q and q not in seen:
            seen.add(q)
            dedup.append(q)
    return dedup


def _offline_domain_keywords(topic_atoms: dict) -> dict:
    """Build a minimal keyword matrix from topic_atoms (no LLM)."""
    kws = copy.deepcopy(_EMPTY_DOMAIN_KEYWORDS)
    for axis in ("method", "object", "task", "scenario"):
        for a in topic_atoms.get(axis) or []:
            if isinstance(a, dict):
                en = a.get("en")
                zh = a.get("zh")
                if en:
                    kws["en"].append(str(en))
                    kws[axis].append(str(en))
                if zh:
                    kws["zh"].append(str(zh))
            elif isinstance(a, str) and a.strip():
                kws["en"].append(a.strip())
                kws[axis].append(a.strip())
    # Dedup.
    for k, v in kws.items():
        if isinstance(v, list):
            seen: set[str] = set()
            dedup: list[str] = []
            for x in v:
                if x and x not in seen:
                    seen.add(x)
                    dedup.append(x)
            kws[k] = dedup
    return kws


# ---------------------------------------------------------------------------
# Prompt: kept inline because it is one self-contained system message.
# ---------------------------------------------------------------------------

_SYSTEM = """你是工科学位论文选题系统中的领域检索侦察 Agent。

你的任务不是给最终结论，而是找出这个题目所在领域应该搜索哪些关键词、baseline、数据集、repo、综述词和避免词。

输入：
- 题目
- 已解析 topic_atoms
- 上一轮正确候选
- 上一轮错误候选
- 上一轮失败 query

你必须：
1. 给出中文和英文关键词。
2. 给出 method/object/task/scenario 四类词。
3. 给出 baseline 搜索词。
4. 给出 dataset 搜索词。
5. 给出 repo 搜索词。
6. 从错误候选中总结 avoid_search。
7. 从正确候选中总结 expansion_terms。

你不得：
1. 直接判定题目可不可做。
2. 直接生成工作包。
3. 只给 YOLO/UNet 这种方法词。
4. 用单一领域规则把题目打到 CV 检测路线。

只输出 JSON。"""


def _build_user_prompt(topic: str, topic_atoms: dict, history: dict) -> str:
    return json.dumps({
        "topic": topic,
        "topic_atoms": topic_atoms,
        "previous_success": history.get("previous_success") or [],
        "previous_noise": history.get("previous_noise") or [],
        "previous_failed_queries": history.get("previous_failed_queries") or [],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# LLM call — uses research_agent._chat_json_strict via the compat shim.
# ---------------------------------------------------------------------------


def _get_chat_strict():
    """Lazy-load ``research_agent._chat_json_strict`` (~2700 line module)."""
    from ._research_agent_compat import chat_json_strict  # type: ignore
    return chat_json_strict


def _parse_llm_payload(raw: Any) -> dict:
    """Coerce LLM output to the strict shape; tolerate string-wrapped JSON."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return _empty_payload(search_notes="LLM returned non-JSON")
    if not isinstance(raw, dict):
        return _empty_payload(search_notes="LLM returned non-dict")
    kws = raw.get("domain_keywords")
    if not isinstance(kws, dict):
        kws = copy.deepcopy(_EMPTY_DOMAIN_KEYWORDS)
    # Coerce each axis to a list[str].
    normalized_kws: dict[str, list[str]] = {}
    for axis, default in _EMPTY_DOMAIN_KEYWORDS.items():
        vals = kws.get(axis) or default
        if not isinstance(vals, list):
            vals = [str(vals)]
        normalized_kws[axis] = [str(v).strip() for v in vals if str(v).strip()]

    def _list(key: str) -> list[str]:
        out = raw.get(key) or []
        if not isinstance(out, list):
            out = [str(out)]
        return [str(v).strip() for v in out if str(v).strip()]

    return {
        "domain_keywords": normalized_kws,
        "must_search": _list("must_search"),
        "avoid_search": _list("avoid_search"),
        "known_baseline_families": _list("known_baseline_families"),
        "known_dataset_families": _list("known_dataset_families"),
        "search_notes": str(raw.get("search_notes") or ""),
    }


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_domain_scout(
    topic: str,
    topic_atoms: dict,
    *,
    llm_client=None,
    history: dict | None = None,
) -> dict:
    """Scout domain keywords for the given topic.

    Returns the strict JSON shape described in SOP §3.2 + §10.1. On
    failure the function still returns a valid shape; the ``must_search``
    list is derived from topic_atoms when possible, otherwise empty.
    """
    history = history or {}
    # 1. Try LLM.
    if llm_client is not None:
        try:
            chat = _get_chat_strict()
            user_prompt = _build_user_prompt(topic, topic_atoms, history)
            raw = chat(
                user_prompt,
                _SYSTEM,
                max_tokens=1500,
                temperature=0.2,
                timeout=60.0,
            )
            parsed = _parse_llm_payload(raw)
            # Trust LLM only when must_search is non-empty.  Empty
            # must_search is a red flag — fall through to offline path.
            if parsed["must_search"]:
                # Augment keyword matrix with topic_atoms (LLM may miss
                # bilingual terms).
                for axis in ("method", "object", "task", "scenario"):
                    for a in topic_atoms.get(axis) or []:
                        if isinstance(a, dict):
                            en = a.get("en")
                            zh = a.get("zh")
                            if en and en not in parsed["domain_keywords"]["en"]:
                                parsed["domain_keywords"]["en"].append(str(en))
                            if zh and zh not in parsed["domain_keywords"]["zh"]:
                                parsed["domain_keywords"]["zh"].append(str(zh))
                return parsed
        except Exception as exc:  # ponytail: never let LLM outage kill the loop
            logger.warning("DomainScout LLM failed, falling back offline: %s", exc)

    # 2. Offline path.
    payload = _empty_payload(search_notes="[Fallback] LLM offline — must_search empty")
    payload["domain_keywords"] = _offline_domain_keywords(topic_atoms)
    payload["must_search"] = _offline_must_search(topic_atoms)
    if not payload["must_search"]:
        payload["search_notes"] = (
            "[Fallback] LLM offline — must_search empty; no English atoms in topic_atoms"
        )
    return payload


__all__ = ["run_domain_scout"]


# ponytail: tiny self-check.
if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def _demo() -> None:
        atoms = {
            "task": [{"en": "underwater acoustic recognition", "zh": "水声识别"}],
            "object": [{"en": "ship-radiated noise", "zh": "船舶辐射噪声"}],
        }
        out = await run_domain_scout(
            "Underwater acoustic target recognition",
            atoms,
            llm_client=None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))

    asyncio.run(_demo())
