"""Topic parser prompt (Re1.2 Agent A1).

Outputs a single topic_atoms dict with:
  method / object / task / scenario / domain (SINGLE string, one of
  CIVIL_INFRA / SIGNAL_TIMESERIES / VISION_2D / VISION_3D / NLP_LLM /
  REMOTE_SENSING / MEDICAL_AI / ENERGY_POWER / CONTROL_MONITORING /
  ROBOTICS_CONTROL / CIVIL_INFRA / UNKNOWN) /
  dataset_terms / baseline_terms / avoid_terms.

The LLM is strongly prohibited from hard-coding well-known dataset/method
names (e.g. "YLO", "SLAM", "COCO") that the topic does not itself imply.
"""
from __future__ import annotations

from typing import Any


DOMAIN_HINT = (
    "One of: signal_timeseries, vision_2d, vision_3d, nlp_llm, "
    "remote_sensing, medical_ai, energy_power, control_monitoring, "
    "robotics_control, civil_infra, unknown."
)


SYSTEM = f"""You parse raw Chinese or English academic topics into structured atoms.

Output STRICT JSON — a single JSON object, no prose, no markdown fences.

Required top-level keys:
- method: list[str]         — techniques the topic implies (e.g. "stereo matching", "U-Net")
- object: list[str]         — physical / behavioral target (e.g. "concrete crack")
- task: list[str]           — action verbs (e.g. "3D reconstruction", "detection")
- scenario: list[str]       — application scenario (e.g. "indoor inspection")
- domain: str               — research field. MUST be a single string, {DOMAIN_HINT}
- dataset_terms: list[str]  — named datasets / benchmarks the topic itself implies
- baseline_terms: list[str] — methods that would serve as baselines for this topic
- avoid_terms: list[str]    — adjacent but out-of-scope terms to avoid

HARD RULES:
1. Do NOT hard-code well-known dataset/method names (e.g. "yolo", "coco",
   "orb-slam", "bert") unless the topic explicitly names them. If the topic
   is a generic task (e.g. "target detection on images"), leave dataset_terms
   and baseline_terms empty rather than guessing.
2. Do NOT pad every key with generic vocabulary. Output [] when no evidence.
3. The `domain` value is a single string from the allowed set — NOT a list.
4. Always return a JSON object even if every list is empty and domain is unknown.
"""

USER_TEMPLATE = """Topic: {topic}

Return the JSON object described by the system prompt."""


def build(topic: str) -> dict[str, str]:
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(topic=topic)}
