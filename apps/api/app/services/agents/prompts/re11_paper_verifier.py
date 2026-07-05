"""Single-candidate paper verifier prompt — permissive + model-portable.

Keeps the system prompt SHORT so reasoner models (step-3.7-flash,
deepseek-reasoner, etc.) still emit JSON to ``content``.  The acceptance
bar is calibrated to produce similar verdict distributions across providers:
~30-40 % accept on real retrieval results.
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You are an academic paper verifier. Evaluate candidates against the topic.
Output a JSON array of verdicts — no prose, no fences."""

USER_TEMPLATE = """Topic: {topic}. Atoms: method={method}, object={object}, task={task}, datasets={dataset_terms}.

Candidates ({n} total):
{candidates_text}

For EACH candidate, decide if it helps a researcher on this topic:
- accept = directly useful: same method+object, or same task+dataset, or a baseline/comparative source
- weak_reject = some relevance but not directly usable (same method different domain, survey, or only generic ML terms)
- reject = unrelated to the topic

Output a JSON array of {n} objects, one per candidate in order:
[{{"title":"<title>","verdict":"<accept|weak_reject|reject>","hit_keywords":["<overlapping terms>"],"relation_to_topic":"<baseline|parallel|survey|none>","reason":"<1 sentence>"}}]

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON array — no prose, no fences."""

# Back-compat single-candidate prompt (kept for tests)
SYSTEM_SINGLE = """You are an academic paper verifier. Evaluate ONE candidate against the topic.
Think step-by-step, then output exactly ONE JSON object — no prose, no list, no fences."""

USER_TEMPLATE_SINGLE = """Topic: {topic}. Atoms: method={method}, object={object}, task={task}, datasets={dataset_terms}.

Candidate:
- Title: {candidates_title}
- Snippet: {candidates_snippet}

Decide if it helps a researcher on this topic:
- accept = directly useful: same method+object, or same task+dataset, or a baseline/comparative source (relation baseline or parallel)
- weak_reject = some relevance but not directly usable (same method different domain, survey mentioning the topic, or only generic ML terms)
- reject = unrelated

Output exactly ONE JSON object:
{{"title":"{candidates_title}","verdict":"<accept|weak_reject|reject>","hit_keywords":["<concrete overlapping terms from title/snippet>"],"relation_to_topic":"<baseline|parallel|survey|none>","reason":"<1 sentence>"}}"""


def build_batch(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]], batch_size: int = 8) -> list[dict[str, str]]:
    """Build batch prompts for verification. Returns list of {system, user} for each batch."""
    prompts: list[dict[str, str]] = []
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        lines: list[str] = []
        for j, c in enumerate(batch):
            title = (c.get("title") or c.get("name") or "").strip()
            snippet = (c.get("abstract") or c.get("description") or "")[:200]
            lines.append(f"[{j}] Title: {title}\n    Snippet: {snippet}")
        prompts.append({
            "system": SYSTEM,
            "user": USER_TEMPLATE.format(
                topic=topic[:200],
                method=_fmt(atoms.get("method")),
                object=_fmt(atoms.get("object")),
                task=_fmt(atoms.get("task")),
                dataset_terms=_fmt(atoms.get("dataset_terms")),
                n=len(batch),
                candidates_text="\n".join(lines),
            ),
        })
    return prompts


def build_one(topic: str, atoms: dict[str, Any], candidate: dict[str, Any]) -> dict[str, str]:
    """Build prompt for exactly one candidate."""
    return {
        "system": SYSTEM_SINGLE,
        "user": USER_TEMPLATE_SINGLE.format(
            topic=topic[:200],
            method=_fmt(atoms.get("method")),
            object=_fmt(atoms.get("object")),
            task=_fmt(atoms.get("task")),
            dataset_terms=_fmt(atoms.get("dataset_terms")),
            candidates_title=(candidate.get("title") or candidate.get("name") or "").strip(),
            candidates_snippet=(candidate.get("abstract")
                                or candidate.get("description") or "")[:250],
        ),
    }


def build(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, str]:
    """Back-compat wrapper."""
    if not candidates:
        return {"system": SYSTEM_SINGLE, "user": "(no candidates)"}
    return build_one(topic, atoms, candidates[0])


def _fmt(v: Any) -> str:
    if not v:
        return "[]"
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)
