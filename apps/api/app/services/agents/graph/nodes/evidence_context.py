"""Re7.6 Evidence Context Compiler — D-08.

Collects verified papers + RAG chunks into structured EvidenceContext objects,
each with stable evidence_id, snippet, location, and role tagging.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.graph.schemas.novelty_schema import EvidenceContext

logger = logging.getLogger(__name__)


def compile_evidence(state: ResearchState) -> list[dict[str, Any]]:
    """Compile evidence contexts from verified papers and baseline candidates."""
    contexts: list[dict[str, Any]] = []
    verified = state.get("verified_papers") or []
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    datasets = state.get("dataset_candidates") or []

    for p in verified:
        pid = p.get("candidate_id") or p.get("paper_id") or p.get("title", "")
        if not pid:
            continue
        abstract = (p.get("abstract") or "")[:500]
        ctx = EvidenceContext(
            candidate_id=str(pid)[:40],
            snippet=abstract,
            location=p.get("url") or p.get("doi") or "",
            role="method",
            source_quality="verified",
        )
        contexts.append(ctx.model_dump())

    for b in baselines[:5]:
        bid = b.get("id") or b.get("title", "")
        if not bid:
            continue
        ctx = EvidenceContext(
            candidate_id=str(bid)[:40],
            snippet=(b.get("abstract") or "")[:300],
            location=b.get("url") or "",
            role="adjacent",
            source_quality="verified",
        )
        contexts.append(ctx.model_dump())

    logger.debug("evidence_context: compiled %d contexts (%d verified, %d baselines)",
                 len(contexts), len(verified), len(baselines))
    return contexts


def evidence_context_node(state: ResearchState) -> dict[str, Any]:
    """LangGraph node: compile evidence contexts for novelty pipeline."""
    return {"evidence_contexts": compile_evidence(state)}


def build_evidence_context_prompt(state: ResearchState) -> str:
    """Build an evidence context summary for LLM prompts."""
    contexts = compile_evidence(state)
    lines = []
    for i, ctx in enumerate(contexts[:20]):
        lines.append(
            f"[evidence-{i}] role={ctx.get('role','?')} source={ctx.get('source_quality','?')}\n"
            f"  snippet: {ctx.get('snippet','')[:200]}\n"
            f"  location: {ctx.get('location','')}"
        )
    return "\n".join(lines) if lines else "no evidence available"
