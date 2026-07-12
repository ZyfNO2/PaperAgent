"""Re7.6 Novelty Draft Generator — D-09.

Transforms raw innovation_points into P-M-I (Problem-Method-Insight)
structured NoveltyCandidate objects with evidence binding.

Key rules (SOP §7.1):
  - Only generates ``draft`` or ``needs_evidence`` status — NEVER ``accepted``
  - Each P/M/I dimension must bind to evidence_ids from EvidenceContext (D-08)
  - Detects pseudo-innovation risks (performance-only insights, first-claim without evidence)
  - Connects to BaselineCard / ModuleCard downstream via stitching_plan
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)

DRAFT_SYSTEM = (
    "You are a research novelty analyst. Given raw innovation points and "
    "evidence contexts, structure each into Problem-Method-Insight format. "
    "Every claim MUST bind to at least one evidence_id. "
    "Status can ONLY be 'draft' or 'needs_evidence' — never 'accepted'. "
    "Output ONLY valid JSON."
)

DRAFT_PROMPT = """Structure raw innovation points into P-M-I novelty candidates.

Topic: {topic}

Raw Innovation Points:
{innovation_json}

Evidence Contexts (verified papers, baselines, RAG chunks):
{evidence_text}

Baseline Candidates:
{baseline_json}

Instructions:
1. For each innovation point, extract or infer:
   - problem: What specific research gap does it address? (not generic "X is important")
   - method: What is the concrete intervention? (not engineering stack description)
   - insight: What conditional finding is expected? (not "F1 improved 5%")
   - scope: Under what conditions does this apply?
2. Bind each candidate to evidence_ids from the Evidence Contexts above.
   - problem → evidence for the gap
   - method → evidence for the approach
   - insight → evidence for the expected outcome
3. Set status:
   - "draft" if all three P/M/I dimensions have at least one evidence_id
   - "needs_evidence" if any dimension lacks evidence
4. Flag pseudo_innovation_risks:
   - "performance_only": insight is just a metric number without mechanism
   - "first_claim_unsupported": claims "first/novel/首次" without evidence
   - "engineering_not_novelty": method is just model swapping
   - "no_differentiation": no clear difference from baseline

Output JSON:
{{
  "novelty_drafts": [
    {{
      "candidate_id": "nd-001",
      "problem": "specific gap description",
      "method": "concrete intervention",
      "insight": "conditional finding beyond metrics",
      "scope": "applicable conditions",
      "evidence_ids": ["ev-0", "ev-1", "ev-2"],
      "status": "draft",
      "pseudo_innovation_risks": []
    }}
  ]
}}

[OUTPUT CONTRACT] Reply ONLY with the JSON object, no prose, no fences."""


def _build_evidence_text(evidence_contexts: list[dict[str, Any]]) -> str:
    """Format evidence contexts for the LLM prompt."""
    if not evidence_contexts:
        return "no evidence available"
    lines = []
    for i, ctx in enumerate(evidence_contexts[:20]):
        if not isinstance(ctx, dict):
            continue
        role = ctx.get("role", "?")
        quality = ctx.get("source_quality", "?")
        snippet = (ctx.get("snippet") or "")[:150]
        loc = ctx.get("location") or ctx.get("candidate_id", "")
        lines.append(f"[ev-{i}] role={role} source={quality} loc={loc}\n  {snippet}")
    return "\n".join(lines) if lines else "no evidence available"


def _build_baseline_text(baselines: list[dict[str, Any]]) -> str:
    """Format baseline candidates for the LLM prompt."""
    if not baselines:
        return "no baselines available"
    lines = []
    for b in baselines[:5]:
        title = b.get("title") or b.get("id", "")
        lines.append(f"- {title}")
    return "\n".join(lines)


def _heuristic_draft(state: ResearchState) -> list[dict[str, Any]]:
    """Fallback: construct drafts from innovation points without LLM."""
    innovation_points = state.get("innovation_points") or []
    evidence_contexts = state.get("evidence_contexts") or []
    baselines = state.get("baseline_candidates") or []

    ev_ids = [
        ctx.get("candidate_id", f"ev-{i}")
        for i, ctx in enumerate(evidence_contexts[:6])
        if isinstance(ctx, dict)
    ]

    def _str(v: Any, default: str = "") -> str:
        """Re7.7: defensive string coercion for state values that may be
        list/dict (e.g. stitching_plan returned as list by LLM)."""
        if v is None:
            return default
        if isinstance(v, str):
            return v
        if isinstance(v, (list, dict)):
            try:
                return json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                return str(v)
        return str(v)

    drafts: list[dict[str, Any]] = []
    for i, ip in enumerate(innovation_points[:5]):
        if not isinstance(ip, dict):
            continue
        desc = _str(ip.get("description", ""))
        baseline = _str(ip.get("baseline_used", ""))
        stitched = ip.get("stitched_modules", [])
        if not isinstance(stitched, list):
            stitched = [str(stitched)] if stitched else []

        problem = f"基于{baseline}的现有方法在{desc}方面存在不足" if baseline else desc
        method = f"借鉴{'、'.join(stitched)}的模块进行拼接改进" if stitched else desc
        insight = _str(ip.get("stitching_plan", ""), "预期通过模块拼接获得性能提升")

        ev_bound = ip.get("candidate_ids") or ev_ids[:3]
        if not isinstance(ev_bound, list):
            ev_bound = [str(ev_bound)] if ev_bound else []
        has_evidence = len(ev_bound) >= 3

        risks: list[str] = []
        if not has_evidence:
            risks.append("insufficient_evidence_binding")
        if any(kw in insight.lower() for kw in ("提高", "提升", "outperform", "achieve")):
            risks.append("performance_only")

        try:
            candidate = NoveltyCandidate(
                candidate_id=f"nd-{i+1:03d}",
                problem=problem[:500],
                method=method[:500],
                insight=insight[:500],
                scope=ip.get("estimated_difficulty", ""),
                evidence_ids=ev_bound[:5],
                status="draft" if has_evidence else "needs_evidence",
                pseudo_innovation_risks=risks,
            )
            drafts.append(candidate.model_dump())
        except Exception as exc:
            logger.debug("heuristic_draft: skipped candidate %d: %s", i, exc)
            drafts.append({
                "candidate_id": f"nd-{i+1:03d}",
                "problem": problem[:200],
                "method": method[:200],
                "insight": insight[:200],
                "scope": "",
                "evidence_ids": ev_bound[:3],
                "status": "needs_evidence",
                "pseudo_innovation_risks": ["validation_failed"],
            })

    if not drafts and baselines:
        b = baselines[0]
        drafts.append({
            "candidate_id": "nd-001",
            "problem": f"需要基于{b.get('title', 'baseline')}的研究空白",
            "method": "待确定",
            "insight": "待确定",
            "scope": "",
            "evidence_ids": ev_ids[:1] if ev_ids else [],
            "status": "needs_evidence",
            "pseudo_innovation_risks": ["no_innovation_extracted"],
        })

    return drafts


def parse_draft_output(raw: dict[str, Any], state: ResearchState) -> list[dict[str, Any]]:
    """Parse LLM output into validated NoveltyCandidate dicts."""
    raw_drafts = raw.get("novelty_drafts", [])
    if not isinstance(raw_drafts, list):
        return _heuristic_draft(state)

    evidence_contexts = state.get("evidence_contexts") or []
    valid_ev_ids = {
        ctx.get("candidate_id", "")
        for ctx in evidence_contexts
        if isinstance(ctx, dict)
    }

    def _as_str(v: Any, default: str = "") -> str:
        """Coerce LLM-returned values to string. Lists/dicts are json-encoded;
        None becomes default. Prevents AttributeError in downstream .lower()
        calls when the model returns a list for problem/method/insight/scope.
        Re7.7: observed on XD-10 where mistral returned insight as a list."""
        if v is None:
            return default
        if isinstance(v, str):
            return v
        if isinstance(v, (list, dict)):
            try:
                return json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                return str(v)
        return str(v)

    drafts: list[dict[str, Any]] = []
    for i, rd in enumerate(raw_drafts):
        if not isinstance(rd, dict):
            continue

        ev_ids = rd.get("evidence_ids", [])
        # Filter evidence_ids to only those in evidence_contexts
        bound_ids = [eid for eid in ev_ids if eid in valid_ev_ids] if valid_ev_ids else ev_ids
        unbound = [eid for eid in ev_ids if eid not in valid_ev_ids] if valid_ev_ids else []

        status = rd.get("status", "needs_evidence")
        # SOP §7.1: NEVER auto-accepted
        if status not in ("draft", "needs_evidence"):
            status = "needs_evidence"

        risks = rd.get("pseudo_innovation_risks", [])
        if unbound:
            risks = list(set(risks + [f"unbound_evidence: {','.join(unbound)}"]))

        # Re7.7: defensive string coercion — LLM may return list/dict for
        # problem/method/insight/scope fields, which would crash
        # NoveltyCandidate._validate_evidence_binding (.lower() on list).
        problem_str = _as_str(rd.get("problem", ""))[:500]
        method_str = _as_str(rd.get("method", ""))[:500]
        insight_str = _as_str(rd.get("insight", ""))[:500]
        scope_str = _as_str(rd.get("scope", ""))

        try:
            candidate = NoveltyCandidate(
                candidate_id=rd.get("candidate_id", f"nd-{i+1:03d}"),
                problem=problem_str,
                method=method_str,
                insight=insight_str,
                scope=scope_str,
                evidence_ids=bound_ids[:10],
                status=status,
                pseudo_innovation_risks=risks,
            )
            drafts.append(candidate.model_dump())
        except Exception as exc:
            logger.debug("parse_draft: candidate %d validation failed: %s", i, exc)
            # Still include but force needs_evidence
            drafts.append({
                "candidate_id": rd.get("candidate_id", f"nd-{i+1:03d}"),
                "problem": problem_str[:200],
                "method": method_str[:200],
                "insight": insight_str[:200],
                "scope": scope_str,
                "evidence_ids": bound_ids[:3],
                "status": "needs_evidence",
                "pseudo_innovation_risks": list(set(risks + ["validation_failed"])),
            })

    return drafts if drafts else _heuristic_draft(state)


def novelty_draft_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: generate P-M-I structured novelty drafts.

    Takes innovation_points + evidence_contexts and produces novelty_drafts.
    Status is always 'draft' or 'needs_evidence' — never 'accepted'.
    """
    t0 = time.time()
    topic = state.get("topic", "")
    innovation_points = state.get("innovation_points") or []
    evidence_contexts = state.get("evidence_contexts") or []
    baselines = state.get("baseline_candidates") or []

    if not innovation_points:
        logger.info("novelty_draft: no innovation points, skipping")
        trace = _emit(
            "novelty_draft", t0,
            {"n_innovation": 0, "n_evidence": len(evidence_contexts)},
            {"n_drafts": 0},
            [{"tool": "skip"}],
            "skip", [],
            state_keys=["novelty_drafts", "trace_events"],
        )
        return {"novelty_drafts": [], "trace_events": [trace]}

    prompt = DRAFT_PROMPT.format(
        topic=topic[:200],
        innovation_json=json.dumps(innovation_points[:5], ensure_ascii=False, default=str)[:3000],
        evidence_text=_build_evidence_text(evidence_contexts),
        baseline_json=_build_baseline_text(baselines),
    )

    prov = "fast_json"
    try:
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        raw = call_json_with_validation(
            prompt,
            system=DRAFT_SYSTEM,
            node_name="novelty_draft",
            profile="fast_json",
            max_tokens=2000,
            timeout=30,
            fallback={"novelty_drafts": _heuristic_draft(state)},
            contract_id="novelty-draft/v1",
        )
        drafts = parse_draft_output(raw, state)
    except Exception as exc:
        logger.warning("novelty_draft: LLM failed: %s — heuristic fallback", exc)
        drafts = _heuristic_draft(state)
        prov = "heuristic"

    n_draft = sum(1 for d in drafts if d.get("status") == "draft")
    n_needs = sum(1 for d in drafts if d.get("status") == "needs_evidence")
    n_risks = sum(len(d.get("pseudo_innovation_risks", [])) for d in drafts)

    trace = _emit(
        "novelty_draft", t0,
        {"n_innovation": len(innovation_points), "n_evidence": len(evidence_contexts)},
        {"n_drafts": len(drafts), "n_draft_status": n_draft,
         "n_needs_evidence": n_needs, "n_risks": n_risks},
        [{"tool": f"novelty_draft.{'llm' if prov != 'heuristic' else 'heuristic'}"}],
        prov, [],
        state_keys=["novelty_drafts", "trace_events"],
    )

    logger.info(
        "novelty_draft: %d drafts (%d draft, %d needs_evidence, %d risks) via %s",
        len(drafts), n_draft, n_needs, n_risks, prov,
    )

    return {"novelty_drafts": drafts, "trace_events": [trace]}
