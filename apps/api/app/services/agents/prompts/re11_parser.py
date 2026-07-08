"""Topic parser prompt (Re1.2 Agent A1).

Outputs a single topic_atoms dict with:
  method / object / task / scenario / domain (SINGLE string, one of
  signal_timeseries / vision_2d / vision_3d / nlp_llm /
  remote_sensing / medical_ai / energy_power / control_monitoring /
  robotics_control / civil_infra / unknown) /
  dataset_terms / baseline_terms / avoid_terms.

The LLM is strongly prohibited from hard-coding well-known dataset/method
names (e.g. "YOLO", "SLAM", "COCO") that the topic does not itself imply.
"""
from __future__ import annotations


DOMAIN_HINT = (
    "One of: signal_timeseries, vision_2d, vision_3d, nlp_llm, "
    "remote_sensing, medical_ai, energy_power, control_monitoring, "
    "robotics_control, civil_infra, unknown."
)


SYSTEM = f"""You parse raw Chinese or English academic topics into structured atoms.

Output STRICT JSON — a single JSON object, no prose, no markdown fences.

Required top-level keys:
- method: list[str]         — techniques the topic implies (e.g. "stereo matching", "transformer")
- object: list[str]         — physical / behavioral target (e.g. "point cloud", "protein structure")
- task: list[str]           — action verbs (e.g. "segmentation", "classification")
- scenario: list[str]       — application scenario (e.g. "autonomous driving", "medical imaging")
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
5. Do NOT bias toward any specific domain. Parse what the topic says, not what
   the examples above suggest. The examples are format-only, not domain hints.
6. **ALL method, object, task, scenario, dataset_terms, baseline_terms, and
   avoid_terms values MUST be in English.** This is critical — Chinese keywords
   will cause downstream search adapters to return zero results.
   When the topic is in Chinese, you MUST translate every technical term to its
   English equivalent. Break down compound Chinese terms into their components.
   Example:
   Input: "基于X方法的Y对象Z任务研究"
   →
       method: ["X method"], object: ["Y object"], task: ["Z task"],
       domain: "unknown"
   Note: The above is a structural template only.
   Parse the ACTUAL topic — do NOT assume any specific domain.
   Always provide at least one method and one task keyword if the topic
   contains any technical content. If a Chinese term has no single English
   equivalent, use multiple keywords to cover its meaning.
"""

USER_TEMPLATE = """Topic: {topic}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str) -> dict[str, str]:
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(topic=topic)}
