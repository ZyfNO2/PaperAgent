"""Re10 ReflectionCriticAgent — SOP §3.2 + §10.2.

Reflects on the previous round's observations and proposes the next
round's action.  Per SOP §3.2 the agent must never mark a missing URL
as a noise failure (the URLRepairAgent owns URL repair).  Per SOP §6.1
empty URL candidates go through URL repair, not the critic.

The critic has a deterministic rule layer that fires when:
  * ``llm_client is None``
  * LLM returns malformed JSON
  * the LLM call raises
The rule layer reads only the ``observations`` dict the
SearchReflectionLoop assembles, so it cannot hallucinate a domain.

ponytail:
- One LLM call per round, max 1200 tokens.
- Diagnosis shape is fixed; rule layer produces the same shape.
- No domain whitelists.  No paper-title blacklists (S66v ban).
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


_SYSTEM = """你是搜索结果反思 Agent。

你要根据上一轮搜索的真实结果，判断为什么没有搜到好证据，下一轮应该怎么改。

输入：
- topic
- topic_atoms
- executed_queries
- accepted_candidates
- noise_candidates
- empty_url_candidates
- failed_queries
- remaining_gaps

你必须识别：
- 查询过泛
- 查询缺对象词
- 查询只含方法词
- source 用错
- URL 缺失但论文可能真实
- 数据集缺口
- baseline 缺口
- repo 缺口
- 占位符 query

你必须输出 next_action：
- repair_query
- repair_url
- expand_from_good_paper
- switch_source
- stop_with_gap

不得把空 URL 直接判为假论文。
不得把 no_results 直接判为题目不可做。

只输出 JSON。"""


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_reflection_critic(
    topic: str,
    topic_atoms: dict,
    observations: dict,
    *,
    llm_client=None,
) -> dict:
    """Reflect on the previous round.

    Returns ``{diagnosis:[{problem, evidence, root_cause, next_action}],
    next_round_focus:[]}``.
    """
    obs = observations or {}
    if llm_client is not None:
        try:
            from ._research_agent_compat import chat_json_strict  # type: ignore
            user_prompt = json.dumps({
                "topic": topic,
                "topic_atoms": topic_atoms,
                "observations": obs,
            }, ensure_ascii=False, indent=2)
            raw = chat_json_strict(
                user_prompt,
                _SYSTEM,
                max_tokens=1200,
                temperature=0.2,
                timeout=60.0,
            )
            parsed = _parse_llm_output(raw)
            if parsed["diagnosis"]:
                return parsed
        except Exception as exc:  # ponytail: never let LLM outage kill the loop
            logger.warning("ReflectionCritic LLM failed, falling back to rules: %s", exc)

    return _rule_layer(obs)


# ---------------------------------------------------------------------------
# Rule layer
# ---------------------------------------------------------------------------


_PROBLEM_TO_ACTION = {
    "dataset_gap": "repair_query",
    "baseline_gap": "repair_query",
    "repo_gap": "repair_query",
    "noise_candidate": "switch_source",
    "empty_url": "repair_url",
    "query_placeholder": "repair_query",
    "source_bias": "switch_source",
    "too_broad_query": "repair_query",
    "too_method_only_query": "repair_query",
    "topic_atom_missing": "stop_with_gap",
}


def _rule_layer(obs: dict) -> dict:
    """Build a diagnosis from observations; never mark empty URL as noise."""
    diagnosis: list[dict] = []
    if obs.get("dataset_gap"):
        diagnosis.append({
            "problem": "dataset_gap",
            "evidence": ["observation.dataset_gap == True"],
            "root_cause": "no dataset/citation surfaced from round 1 search",
            "next_action": "repair_query",
        })
    if obs.get("baseline_gap"):
        diagnosis.append({
            "problem": "baseline_gap",
            "evidence": ["observation.baseline_gap == True"],
            "root_cause": "no baseline/citation surfaced from round 1 search",
            "next_action": "repair_query",
        })
    if obs.get("repo_gap"):
        diagnosis.append({
            "problem": "repo_gap",
            "evidence": ["observation.repo_gap == True"],
            "root_cause": "no github/repo surfaced from round 1 search",
            "next_action": "repair_query",
        })

    placeholder_leaks = obs.get("query_placeholder_leaks") or []
    for ph in placeholder_leaks:
        diagnosis.append({
            "problem": "query_placeholder",
            "evidence": [f"query={ph!r}"],
            "root_cause": "planner emitted unsubstituted placeholder; atom missing",
            "next_action": "repair_query",
        })

    noise = obs.get("noise_candidates") or []
    if noise:
        diagnosis.append({
            "problem": "noise_candidate",
            "evidence": [str(n) for n in noise[:3]],
            "root_cause": "off-topic hits; query too broad or source biased",
            "next_action": _PROBLEM_TO_ACTION["noise_candidate"],
        })

    # SOP §6.1 — empty URL is NOT noise. Tag as repair_url, never noise.
    empty_url_n = len(obs.get("empty_url_candidates") or [])
    if empty_url_n:
        diagnosis.append({
            "problem": "empty_url",
            "evidence": [f"{empty_url_n} candidates with empty URL"],
            "root_cause": "OpenAlex returned no landing page; URL repairable",
            "next_action": "repair_url",
        })

    failed_q = obs.get("failed_queries") or []
    if failed_q:
        diagnosis.append({
            "problem": "source_bias",
            "evidence": [str(q) for q in failed_q[:3]],
            "root_cause": "adapter returned empty; try a different source",
            "next_action": "switch_source",
        })

    next_round_focus = _derive_focus(obs, diagnosis)
    return {
        "diagnosis": diagnosis,
        "next_round_focus": next_round_focus,
    }


def _derive_focus(obs: dict, diagnosis: list[dict]) -> list[str]:
    focus: list[str] = []
    problems = {d.get("problem") for d in diagnosis}
    if "dataset_gap" in problems:
        focus.append("dataset search with object term + 'benchmark'")
    if "baseline_gap" in problems:
        focus.append("baseline search with method+object term")
    if "repo_gap" in problems:
        focus.append("github search with object + task + 'implementation'")
    if "query_placeholder" in problems:
        focus.append("drop or repair placeholder queries before adapter call")
    if "noise_candidate" in problems:
        focus.append("narrow query: require object + task, drop method-only")
    if "empty_url" in problems:
        focus.append("run URLRepairAgent on empty-URL candidates")
    if not focus:
        focus.append("continue current plan; no new gaps detected")
    return focus


# ---------------------------------------------------------------------------
# LLM output normalization
# ---------------------------------------------------------------------------


def _parse_llm_output(raw: Any) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {"diagnosis": [], "next_round_focus": []}
    if not isinstance(raw, dict):
        return {"diagnosis": [], "next_round_focus": []}
    diag_in = raw.get("diagnosis") or []
    if not isinstance(diag_in, list):
        diag_in = []
    diagnosis: list[dict] = []
    for d in diag_in:
        if not isinstance(d, dict):
            continue
        problem = str(d.get("problem") or "")
        # Defensive: drop any diagnosis that calls empty URL "noise".
        if problem == "noise_candidate" and "url" in str(d.get("root_cause", "")).lower():
            continue
        next_action = str(d.get("next_action") or "")
        if next_action not in {
            "repair_query", "repair_url", "expand_from_good_paper",
            "switch_source", "stop",
        }:
            next_action = _PROBLEM_TO_ACTION.get(problem, "switch_source")
        diagnosis.append({
            "problem": problem,
            "evidence": [str(e) for e in (d.get("evidence") or [])][:5],
            "root_cause": str(d.get("root_cause") or ""),
            "next_action": next_action,
        })
    focus = raw.get("next_round_focus") or []
    if not isinstance(focus, list):
        focus = []
    return {
        "diagnosis": diagnosis,
        "next_round_focus": [str(x) for x in focus][:8],
    }


__all__ = ["run_reflection_critic"]


# ponytail: tiny self-check.
if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def _demo() -> None:
        out = await run_reflection_critic(
            "Underwater acoustic target recognition",
            {"task": [{"en": "underwater acoustic recognition"}]},
            observations={"dataset_gap": True, "baseline_gap": True, "empty_url_candidates": ["x"]},
            llm_client=None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))

    asyncio.run(_demo())
