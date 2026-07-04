"""Topic parser prompt (Re1.1 Search Planner Prompt §8.1 — atoms part).

Outputs topic_atoms with: method / object / task / scenario / domain /
dataset_terms / baseline_terms / avoid_terms.
"""
from __future__ import annotations

from typing import Any


SYSTEM = """You parse raw Chinese or English thesis topics into structured atoms.
Output STRICT JSON. Do not invent methods, datasets, or baselines that the
topic does not imply. Avoid generic method names (e.g. "deep learning",
"neural network") unless the topic truly is generic."""

USER_TEMPLATE = """Topic: {topic}
Constraints: {constraints}

Return JSON with exactly these keys:
- method: list[str] — techniques implied (e.g. "stereo matching", "U-Net")
- object: list[str] — physical/behavioral target (e.g. "concrete crack")
- task: list[str] — what to do (e.g. "3D reconstruction", "detection")
- scenario: list[str] — application scenario ("industrial inspection")
- domain: list[str] — field ("computer vision", "structural engineering")
- dataset_terms: list[str] — named datasets/benchmarks suggested by the topic
- baseline_terms: list[str] — methods that would serve as baselines
- avoid_terms: list[str] — adjacent but out-of-scope terms
- languages: list[str] — query languages to use, default ["en"]

Do not pad. If a field has no evidence, return [] for it."""


def build(topic: str, constraints: dict[str, Any] | None = None) -> dict[str, str]:
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            constraints=constraints or {},
        ),
    }
