"""Paper verifier prompt (Re1.1 §8 / §10).

For each candidate, decide accept / weak_reject / reject against the topic
and produce per-keyword match breakdown (命中 / 无关 / 相关).

Output schema per candidate:
  title / verdict / hit_keywords / unrelated_keywords / related_keywords /
  source_type / relation_to_topic / url_missing / needs_human_confirm /
  reason
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You verify whether each candidate paper actually serves the topic.
You MUST NOT fabricate titles or overstate relevance. Drop any candidate whose
title does not appear in the source evidence.

For each candidate produce: hit_keywords, unrelated_keywords, related_keywords,
source_type (paper/dataset/repo/survey), relation_to_topic (direct/parallel/
baseline/survey/none), url_missing (bool), needs_human_confirm (bool), reason.
Reject when relation_to_topic == none OR no hit_keywords.
Weak-reject when hit_keywords exist but only via generic terms."""

USER_TEMPLATE = """Topic: {topic}
Atoms (baselines/dataset/avoid from the parsed topic):
- method: {method}
- object: {object}
- task: {task}
- dataset_terms: {dataset_terms}
- baseline_terms: {baseline_terms}
- avoid_terms: {avoid_terms}

Candidates to verify (each with snippet):
{candidates_block}

Return JSON: list of objects with these keys:
 title, verdict (accept|weak_reject|reject), hit_keywords, unrelated_keywords,
 related_keywords, source_type, relation_to_topic, url_missing,
 needs_human_confirm, reason"""


def build(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, str]:
    def snippet(c: dict[str, Any]) -> str:
        title = c.get("title") or c.get("name") or ""
        abstract = (c.get("abstract") or c.get("description") or "")[:300]
        src = c.get("source") or c.get("origin") or "?"
        return f"- [{src}] {title}\\n  {abstract}"

    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            method=atoms.get("method") or [],
            object=atoms.get("object") or [],
            task=atoms.get("task") or [],
            dataset_terms=atoms.get("dataset_terms") or [],
            baseline_terms=atoms.get("baseline_terms") or [],
            avoid_terms=atoms.get("avoid_terms") or [],
            candidates_block="\n".join(snippet(c) for c in candidates) or "(none)",
        ),
    }
