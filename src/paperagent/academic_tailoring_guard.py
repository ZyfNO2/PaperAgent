from __future__ import annotations

from paperagent import academic_tailoring as _implementation
from paperagent.academic_tailoring import (
    TailoredResearchProposal,
    TailoringDecision,
    TailoringTask,
)

_base_compose = _implementation.compose_tailored_research_proposal

_WEAK_NOVELTY_PHRASES = {
    "combine two existing modules",
    "add two modules",
    "module combination",
    "the modules are combined",
    "combine modules",
}


def _is_weak_novelty(value: str) -> bool:
    return value.strip().lower() in _WEAK_NOVELTY_PHRASES


def compose_tailored_research_proposal(task: TailoringTask) -> TailoredResearchProposal:
    proposal = _base_compose(task)
    weak = _is_weak_novelty(task.novelty_thesis) or _is_weak_novelty(
        task.why_not_simple_splice
    )
    if not weak or proposal.decision is TailoringDecision.NO_GO:
        return proposal
    risk = (
        "novelty is stated as module composition rather than a falsifiable "
        "problem-method-insight contribution"
    )
    return proposal.model_copy(
        update={
            "decision": TailoringDecision.REVISE,
            "strongest_reason": risk,
            "risks": (*proposal.risks, risk),
        }
    )


_implementation.compose_tailored_research_proposal = compose_tailored_research_proposal

__all__ = ["compose_tailored_research_proposal"]
