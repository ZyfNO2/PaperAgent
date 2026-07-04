"""Work package brainstorm prompt (Re1.1 §11).

Generate research work packages ONLY from classified evidence. Each package:
research_question / baseline / improved_module_source / data_source /
experiment_metrics / risk / estimated_workload.

When evidence is insufficient, output a repair plan (what's missing + next
tool calls fabricated), not a fabricated work package.
"""
from __future__ import annotations

from typing import Any

SYSTEM = """You propose research work packages grounded in the cited papers,
parallel papers, datasets, and repos. Do NOT invent baselines or modules.
Every reference you name MUST appear in the evidence.

If evidence is insufficient, output an `evidence_gap` describing what is missing
and the next-round repair tool calls (tool_name + query + expected_evidence)."""

USER_TEMPLATE = """Topic: {topic}
Topic atoms: {atoms}

Classified evidence:
- baselines: {baselines}
- parallels: {parallels}
- datasets: {datasets}
- repos: {repos}

Constraints (user): {constraints}

Return JSON:
- work_packages: list of objects with:
    * title
    * research_question
    * baseline (a title cited from evidence)
    * improved_module_source (a title from evidence, or null if absent)
    * data_source (a dataset name from evidence, or null)
    * experiment_metrics (a title where metrics are defined)
    * risk
    * estimated_workload
- evidence_gap: list of objects with "missing" and "tool_calls"
    where each tool_call has tool_name / query / expected_evidence;
    non-empty when work_packages cannot be grounded."""


def build(
    topic: str,
    atoms: dict[str, Any],
    *,
    baselines: list[dict[str, Any]],
    parallels: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    repos: list[dict[str, Any]],
    constraints: dict[str, Any] | None = None,
) -> dict[str, str]:
    def shorten(items: list[dict[str, Any]]) -> list[str]:
        return [
            c.get("title") or c.get("name") or c.get("id") or "?"
            for c in items[:12]
        ]

    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            topic=topic,
            atoms=atoms,
            baselines=shorten(baselines),
            parallels=shorten(parallels),
            datasets=shorten(datasets),
            repos=shorten(repos),
            constraints=constraints or {},
        ),
    }
