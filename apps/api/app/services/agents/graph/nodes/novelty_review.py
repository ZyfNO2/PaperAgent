"""Re6.4 / Re8.0 WP5 Novelty Review — The reviewer pressure-test adapter.

Re8.0 WP5 enhancement: adds Problem-Method-Insight (P-M-I) structure,
multi-granularity contributions, falsifiable hypothesis, minimum key
experiment, and contribution type per ``Plan/...Re8.0...md`` §9.2.

All new fields are additive — existing consumers that only read
``novelty_review_verdict`` / ``novelty_review_score`` / ``pressure_points``
keep working unchanged. The new fields default to empty/``"unknown"``
when the LLM omits them, so schema stability holds across model switches.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)

# Re8.0 WP5: allowed contribution types (§1.1 product boundary)
CONTRIBUTION_TYPES = (
    "methodological",
    "engineering",
    "application",
    "system_integration",
    "empirical",
    "reproduction",
)
_REVIEW_VERDICTS = ("accepted", "weak_reject", "reject")

NOVELTY_REVIEW_SYSTEM = (
    "You are an anonymous reviewer evaluating research novelty claims. "
    "Perform a rigorous pressure test across 5 dimensions. "
    "Every criticism MUST cite an evidence_id from the input. "
    "If no evidence exists for a dimension, write 'unknown' as evidence_id. "
    "Output ONLY valid JSON."
)

NOVELTY_REVIEW_PROMPT = """Evaluate the novelty candidate against 5 reviewer dimensions.

Topic: {topic}

Novelty Candidate:
{novelty_json}

Evidence Context (papers, chunks, verified facts):
{evidence_context}

Tailored Method (if available):
{tailored_method_context}

---

For each dimension, provide a reviewer pressure point:

1. **repetition**: Is this approach already published? Does it genuinely differ from prior work?
2. **motivation**: Is the problem gap real and supported by evidence? Or is it motivation by model-availability?
3. **falsifiability**: Can the claims be disproven? What experiment would refute them?
4. **differentiation**: How does each module actually differ from baselines (not just "we added X")?
5. **story**: Does the narrative connect Problem→Method→Insight logically without gaps?

Additionally, produce the Re8.0 P-M-I fields (§9.2):

- **problem_method_insight**: identify (a) which observable failure mode remains
  unsolved, (b) which explicit mechanism responds to it, (c) what generalizable
  knowledge the experiment hopes to reveal.
- **contributions**: write the contribution at three granularities — one
  sentence, three sentences, and a full paragraph. Use "proposed" / "expected"
  wording; do NOT describe unrun experiments as completed.
- **falsifiable_hypothesis**: a single falsifiable statement an experiment
  could refute.
- **minimum_key_experiment**: the smallest experiment that would distinguish
  the proposed mechanism from the baseline.
- **contribution_type**: one of {contribution_types} — pick the most honest
  fit; downgrade to engineering/application/empirical if methodological
  novelty is weak.

Output JSON:
{{
  "verdict": "accepted" | "weak_reject" | "reject",
  "novelty_score": 0-10,
  "pseudo_innovation_risks": ["risk1", "risk2"],
  "pressure_points": [
    {{
      "risk": "repetition" | "motivation" | "falsifiability" | "differentiation" | "story",
      "question": "reviewer question",
      "severity": "high" | "medium" | "low",
      "repair": "suggested fix",
      "evidence_ids": ["id1", "id2"]
    }}
  ],
  "differentiation_matrix": [
    {{
      "adjacent_work_id": "paper_id",
      "adjacent_work_label": "Paper Title",
      "problem_diff": "...",
      "method_diff": "...",
      "detail_diff": "...",
      "evidence_diff": "...",
      "insight_diff": "..."
    }}
  ],
  "required_repairs": ["repair1", "repair2"],
  "strengths": ["strength1"],
  "risks": ["risk1"],
  "problem_method_insight": {{
    "problem": "observable failure mode still unsolved",
    "method": "explicit mechanism that responds to it",
    "insight": "generalizable knowledge the experiment hopes to reveal"
  }},
  "contributions": {{
    "one_sentence": "...",
    "three_sentence": "...",
    "paragraph": "..."
  }},
  "falsifiable_hypothesis": "...",
  "minimum_key_experiment": "...",
  "contribution_type": "methodological" | "engineering" | "application" | "system_integration" | "empirical" | "reproduction"
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


def _format_tailored_method_context(tailored: dict[str, Any] | None) -> str:
    if not tailored or not isinstance(tailored, dict):
        return "(no tailored method available — topic_only path)"
    primary = tailored.get("primary_baseline", {}) or {}
    modules = tailored.get("candidate_modules", []) or []
    verdict = tailored.get("verdict", "unknown")
    mod_str = "; ".join(m.get("name", "") for m in modules[:3] if isinstance(m, dict))
    return (
        f"verdict={verdict}; primary_baseline={primary.get('title', '')[:100]}; "
        f"modules=[{mod_str[:200]}]"
    )


def build_novelty_review_prompt(state: ResearchState) -> str:
    topic = state.get("topic", "")
    innovation_points = state.get("innovation_points", [])
    verified_papers = state.get("verified_papers", [])
    baseline_candidates = state.get("baseline_candidates", [])
    tailored_method = state.get("tailored_method")

    evidence_parts: list[str] = []
    for paper in verified_papers[:10]:
        evidence_parts.append(
            f"[{paper.get('candidate_id', 'unknown')}] {paper.get('title', '')} "
            f"({paper.get('year', '')}) — {str(paper.get('abstract', ''))[:200]}"
        )
    for paper in (baseline_candidates or [])[:5]:
        evidence_parts.append(
            f"[{paper.get('id', 'unknown')}] {paper.get('title', '')} (baseline)"
        )

    novelty_json = json.dumps(
        {"innovation_points": innovation_points},
        ensure_ascii=False, default=str,
    )[:4000]

    return NOVELTY_REVIEW_PROMPT.format(
        topic=topic,
        novelty_json=novelty_json,
        evidence_context="\n".join(evidence_parts) if evidence_parts else "no evidence available",
        tailored_method_context=_format_tailored_method_context(tailored_method),
        contribution_types=" | ".join(CONTRIBUTION_TYPES),
    )


# ── Schema enforcement (WP5: model-switch stability) ──────────────────────


def _clamp_verdict(raw: Any) -> str:
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in _REVIEW_VERDICTS:
            return v
        if "accept" in v:
            return "accepted"
        if "weak" in v or "revise" in v:
            return "weak_reject"
        if "reject" in v:
            return "reject"
    return "reject"


def _clamp_contribution_type(raw: Any) -> str:
    if isinstance(raw, str):
        c = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if c in CONTRIBUTION_TYPES:
            return c
    return "engineering"  # §1.1: honest downgrade when novelty is weak


def _clamp_score(raw: Any) -> int:
    try:
        s = int(raw)
        return max(0, min(10, s))
    except (TypeError, ValueError):
        return 0


def _normalize_pmi(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raw = {}
    return {
        "problem": str(raw.get("problem", "")) or "unspecified",
        "method": str(raw.get("method", "")) or "unspecified",
        "insight": str(raw.get("insight", "")) or "unspecified",
    }


def _normalize_contributions(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raw = {}
    return {
        "one_sentence": str(raw.get("one_sentence", "")) or "unspecified",
        "three_sentence": str(raw.get("three_sentence", "")) or "unspecified",
        "paragraph": str(raw.get("paragraph", "")) or "unspecified",
    }


def _ensure_str_list(raw: Any, max_items: int = 20) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw[:max_items] if x is not None]


def _ensure_dict_list(raw: Any, max_items: int = 20) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [x for x in raw[:max_items] if isinstance(x, dict)]


def normalize_review_output(raw: dict[str, Any], *, generated_by: str = "llm") -> dict[str, Any]:
    """Enforce Review schema regardless of which model produced ``raw``.

    This is the single chokepoint that guarantees schema stability across
    model switches (WP5 acceptance: "切换至少三类模型时 Schema 稳定").
    """
    return {
        # ── existing fields (backward compat) ──
        "novelty_review_verdict": _clamp_verdict(raw.get("verdict")),
        "novelty_review_score": _clamp_score(raw.get("novelty_score")),
        "pseudo_innovation_risks": _ensure_str_list(raw.get("pseudo_innovation_risks")),
        "pressure_points": _ensure_dict_list(raw.get("pressure_points")),
        "differentiation_matrix": _ensure_dict_list(raw.get("differentiation_matrix")),
        "required_repairs": _ensure_str_list(raw.get("required_repairs")),
        "review_strengths": _ensure_str_list(raw.get("strengths")),
        "review_risks": _ensure_str_list(raw.get("risks")),
        # ── Re8.0 WP5 new fields (§9.2) ──
        "problem_method_insight": _normalize_pmi(raw.get("problem_method_insight")),
        "contributions": _normalize_contributions(raw.get("contributions")),
        "falsifiable_hypothesis": str(raw.get("falsifiable_hypothesis", "")) or "unspecified",
        "minimum_key_experiment": str(raw.get("minimum_key_experiment", "")) or "unspecified",
        "contribution_type": _clamp_contribution_type(raw.get("contribution_type")),
        "review_generated_by": generated_by,
    }


def parse_novelty_review_output(raw: dict[str, Any]) -> dict[str, Any]:
    """Backward-compat parser — delegates to normalize_review_output.

    Existing callers that import this function keep working; new callers
    should prefer ``normalize_review_output`` directly.
    """
    return normalize_review_output(raw, generated_by="llm")


def _empty_review(*, generated_by: str = "fallback",
                  risks: list[str] | None = None,
                  error: str | None = None) -> dict[str, Any]:
    """Build an empty review with all schema fields populated.

    Used for both the no-innovation-points early exit and the LLM-failure
    fallback path. Marks ``review_generated_by`` so Claim Judge knows not
    to trust a fallback review.
    """
    out = normalize_review_output({}, generated_by=generated_by)
    if risks:
        out["pseudo_innovation_risks"] = list(risks)
    if error:
        out["novelty_review_error"] = error
    return out


def novelty_review_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: run the novelty reviewer pressure test.

    Reads innovation_points from state, calls LLM, returns parsed review.
    If no innovation points, returns empty review without LLM call.

    Re8.0 WP5: if ``tailored_method`` is in state (seeded_research path),
    the prompt includes it so the reviewer can pressure-test the tailored
    assembly, not just the raw innovation points. Falls back gracefully
    when ``tailored_method`` is absent (topic_only path).

    Re8.0 WP5 fixup (P1-1): all three return paths now emit a trace_events
    entry with provider / verdict / generated_by for debuggability, parity
    with tailor_skill_adapter_node.
    """
    t0 = time.time()
    innovation_points = state.get("innovation_points", [])

    if not innovation_points:
        logger.info("novelty_review: no innovation points, skipping LLM call")
        result = _empty_review(generated_by="fallback",
                               risks=["no_innovation_points"])
        trace = _emit(
            "novelty_review", t0,
            {"n_innovation_points": 0},
            {"verdict": result["novelty_review_verdict"],
             "generated_by": result["review_generated_by"],
             "score": result["novelty_review_score"]},
            [], "n/a", [],
            state_keys=["novelty_review_verdict", "novelty_review_score",
                        "review_generated_by", "trace_events"],
        )
        result["trace_events"] = [trace]
        return result

    prompt = build_novelty_review_prompt(state)
    prov = "premium_review"

    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=NOVELTY_REVIEW_SYSTEM,
            node_name="novelty_review",
            profile="premium_review",
            contract_id="novelty-review/v1",
            max_tokens=3000,
            timeout=60.0,
            fallback={
                "verdict": "reject",
                "novelty_score": 0,
                "pseudo_innovation_risks": ["llm_unavailable"],
                "pressure_points": [],
                "differentiation_matrix": [],
                "required_repairs": [],
                "strengths": [],
                "risks": [],
                "problem_method_insight": {"problem": "", "method": "", "insight": ""},
                "contributions": {"one_sentence": "", "three_sentence": "", "paragraph": ""},
                "falsifiable_hypothesis": "",
                "minimum_key_experiment": "",
                "contribution_type": "engineering",
            },
        )
        # If fallback dict came back, mark generated_by accordingly
        generated_by = "llm"
        if not isinstance(raw, dict):
            logger.warning("novelty_review: LLM returned non-dict, using empty review")
            result = _empty_review(generated_by="fallback", risks=["llm_unavailable"])
            prov = "fallback"
        else:
            # Detect the fallback dict shape (LLMUnavailable path)
            if raw.get("pseudo_innovation_risks") == ["llm_unavailable"]:
                generated_by = "fallback"
                prov = "fallback"
            result = normalize_review_output(raw, generated_by=generated_by)
        logger.info("novelty_review: verdict=%s score=%s type=%s generated_by=%s",
                     result["novelty_review_verdict"],
                     result["novelty_review_score"],
                     result["contribution_type"],
                     result["review_generated_by"])
    except Exception as exc:
        logger.warning("novelty_review: LLM call failed: %s", exc)
        result = _empty_review(generated_by="fallback",
                               risks=["llm_unavailable"],
                               error=str(exc))
        prov = "fallback"

    trace = _emit(
        "novelty_review", t0,
        {"n_innovation_points": len(innovation_points),
         "has_tailored_method": bool(state.get("tailored_method"))},
        {"verdict": result["novelty_review_verdict"],
         "generated_by": result["review_generated_by"],
         "score": result["novelty_review_score"],
         "contribution_type": result["contribution_type"]},
        [{"tool": "novelty-review/v1" if prov != "fallback" else "rule-fallback"}],
        prov, [],
        state_keys=["novelty_review_verdict", "novelty_review_score",
                    "problem_method_insight", "contributions",
                    "falsifiable_hypothesis", "minimum_key_experiment",
                    "contribution_type", "review_generated_by",
                    "trace_events"],
    )
    result["trace_events"] = [trace]
    return result
