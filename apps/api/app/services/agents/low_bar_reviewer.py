"""Low-bar Reviewer — minimal pre-synthesis gate (Re02 Task 6).

Five (well, seven in the SOP) lightweight checks; nothing formal:

1. Topic boundary — is the topic bounded enough?
2. Baseline candidate present (or explicit baseline_gap).
3. Data-source candidate present (or explicit data_gap).
4. Several reference papers (or explicit continue_search_direction).
5. Work suggestions bound to evidence (not template boilerplate).
6. Long-tail candidates from references / repo descriptions survived.
7. Weak-but-real candidates shown as candidate / needs_manual, not dropped.

LLM call returns a structured verdict; when LLM is dead, we run a
deterministic local check so the agent never silently "passes" the
gate.

Ponytail: one LLM call + deterministic fallback. ~100 lines.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLMUnavailable
from .prompts import USER_TEMPLATE_LOW_BAR, LOW_BAR_REVIEWER_SYSTEM

logger = logging.getLogger(__name__)


VALID_VERDICT = {"pass", "needs_revision", "stop"}


@dataclass
class LowBarVerdict:
    review_verdict: str = "needs_revision"
    blocking_questions: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)
    can_continue_to_opening_report: bool = False
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_verdict": self.review_verdict,
            "blocking_questions": list(self.blocking_questions),
            "weak_points": list(self.weak_points),
            "can_continue_to_opening_report": self.can_continue_to_opening_report,
            "summary": self.summary,
        }


def run_low_bar_review(
    *,
    parsed_topic: dict,
    synthesize_output: dict,
    evidence_review_stats: dict[str, int],
    candidate_pool_stats: dict[str, int],
    chat_json_strict,
    llm_blocker: str | None = None,
) -> LowBarVerdict:
    """5-dim lightweight gate. `chat_json_strict` is the injected LLM wrapper.

    Re03 SOP §4.4: if `llm_blocker` is set (e.g. ER chunk failed JSON parse
    → `evidence_review_parse_failed`), the gate MUST refuse `pass` because
    the LLM-driven evidence tiers are unverified. The deterministic
    fallback path also honors this.
    """
    summary_block = json.dumps(
        {
            "direction_recommendation": synthesize_output.get("direction_recommendation", "")[:500],
            "baseline_options": synthesize_output.get("baseline_options", []),
            "paper_groups": synthesize_output.get("paper_groups", {}),
            "evidence_gaps": synthesize_output.get("evidence_gaps", []),
            "work_suggestions": synthesize_output.get("work_suggestions", []),
            "manual_questions": synthesize_output.get("manual_questions", []),
            "evidence_review_stats": evidence_review_stats,
            "candidate_pool_stats": candidate_pool_stats,
            "llm_blocker": llm_blocker,
        },
        ensure_ascii=False,
    )
    prompt = USER_TEMPLATE_LOW_BAR.format(
        parsed_topic=json.dumps(parsed_topic, ensure_ascii=False),
        summary_block=summary_block,
    )

    try:
        out = chat_json_strict(prompt, LOW_BAR_REVIEWER_SYSTEM, max_tokens=1800)
    except LLMUnavailable as exc:
        logger.warning("Low-bar reviewer LLM unavailable: %s — deterministic fallback", exc)
        return _deterministic_verdict(
            synthesize_output, evidence_review_stats, candidate_pool_stats,
        )

    verdict = str(out.get("review_verdict") or "needs_revision").strip().lower()
    if verdict not in VALID_VERDICT:
        verdict = "needs_revision"
    weak_points = [str(w) for w in (out.get("weak_points") or [])][:5]

    # Re03 SOP §4.4: if any upstream LLM stage set an llm_blocker, the gate
    # MUST refuse pass regardless of the LLM's own verdict.
    if llm_blocker and verdict == "pass":
        verdict = "needs_revision"
        weak_points = ([f"llm_blocker present: {llm_blocker}"] + weak_points)[:5]

    return LowBarVerdict(
        review_verdict=verdict,
        blocking_questions=[str(q) for q in (out.get("blocking_questions") or [])][:5],
        weak_points=weak_points,
        can_continue_to_opening_report=bool(out.get("can_continue_to_opening_report", False)) and not llm_blocker,
        summary=str(out.get("summary") or "")[:400],
    )


def _deterministic_verdict(
    synthesize_output: dict,
    er_stats: dict[str, int],
    cp_stats: dict[str, int],
    llm_blocker: str | None = None,
) -> LowBarVerdict:
    """No-LLM gate. Returns needs_revision when evidence is thin.

    Re03: if llm_blocker is set, ALWAYS return needs_revision (never
    pass). Heuristic fallback is not a license to skip the audit.
    """
    paper_groups = synthesize_output.get("paper_groups") or {}
    baseline = paper_groups.get("baseline") or []
    parallel = paper_groups.get("parallel") or []
    reference = paper_groups.get("reference") or []
    long_tail = paper_groups.get("long_tail_candidates") or []

    weak: list[str] = []
    questions: list[str] = []

    if llm_blocker:
        weak.insert(0, f"llm_blocker present: {llm_blocker} → refuse pass")

    if not baseline:
        weak.append("no baseline candidate surfaced; cannot recommend method route")
        questions.append("Which baseline method family are you considering (YOLO / U-Net / Transformer / classic)?")
    if not reference and not long_tail:
        weak.append("no reference / long-tail candidates; literature body too thin")
    core_n = er_stats.get("core", 0)
    rejected_n = er_stats.get("rejected", 0)
    if core_n == 0:
        weak.append("zero core-tier candidates from evidence audit")
        questions.append("Is the topic scope too narrow? Consider broadening the research direction.")
    if rejected_n > 0 and core_n == 0:
        weak.append("candidates are being rejected without core tier rising — review direction")

    has_data = bool(cp_stats.get("dataset") or cp_stats.get("paper"))
    if not has_data:
        weak.append("no paper / dataset candidates in pool — multi-round retrieval may have failed")

    can_continue = (
        bool(baseline) and core_n > 0 and len(weak) <= 1 and not llm_blocker
    )
    verdict = "pass" if can_continue else "needs_revision"

    summary = (
        f"heuristic: baseline={len(baseline)}, parallel={len(parallel)}, "
        f"reference={len(reference)}, long_tail={len(long_tail)}; "
        f"core={core_n}, needs_manual={er_stats.get('needs_manual', 0)}, "
        f"rejected={rejected_n}; pool={cp_stats}; llm_blocker={llm_blocker or 'none'}"
    )
    return LowBarVerdict(
        review_verdict=verdict,
        blocking_questions=questions[:5],
        weak_points=weak[:5],
        can_continue_to_opening_report=can_continue,
        summary=summary,
    )
