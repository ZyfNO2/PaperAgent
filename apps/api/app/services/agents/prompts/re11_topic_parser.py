"""Topic parser prompt (Re1.1 Search Planner Prompt §8.1 — atoms part).

Outputs topic_atoms with: method / object / task / scenario / domain /
dataset_terms / baseline_terms / avoid_terms.
"""
from __future__ import annotations

from typing import Any


SYSTEM = """You parse raw Chinese or English thesis topics into structured atoms.
Output STRICT JSON. Do not invent methods, datasets, or baselines that the
topic does not imply. Avoid generic method names (e.g. "deep learning",
"neural network") unless the topic truly is generic.

Do NOT bias toward any specific domain. Parse what the topic says, not what
examples suggest. If the topic says <object_X>, every alias must refer to
<object_X> or its direct synonyms — never to <object_Y> from an adjacent
field that happens to share a keyword.
"""

USER_TEMPLATE = """Topic: {topic}
Constraints: {constraints}

Return JSON with exactly these keys:
- method: list[str] — techniques the topic implies (e.g. "stereo matching", "transformer")
- object: list[str] — physical/behavioral target (e.g. "point cloud", "protein structure")
- task: list[str] — what to do (e.g. "segmentation", "classification")
- scenario: list[str] — application scenario (e.g. "autonomous driving", "medical imaging")
- domain: list[str] — field ("computer vision", "structural engineering")
- dataset_terms: list[str] — named datasets/benchmarks suggested by the topic
- baseline_terms: list[str] — methods that would serve as baselines
- avoid_terms: list[str] — adjacent but out-of-scope terms
- languages: list[str] — query languages to use, default ["en"]

Do not pad. If a field has no evidence, return [] for it.
Do NOT bias toward any specific domain. Parse what the topic says.
[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, constraints: dict[str, Any] | None = None) -> dict[str, str]:
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            constraints=constraints or {},
        ),
    }
