"""Compatibility surface for audited academic tailoring proposals.

The implementation moved to :mod:`paperagent.academic_tailoring_proposal` so
proposal generation and the canonical methodology audit share one source of
truth. Existing imports remain stable.
"""

from paperagent.academic_tailoring_proposal import (
    PROPOSAL_POLICY_VERSION,
    AcademicStory,
    BaselineProposal,
    BaselineReproduction,
    EvidenceScope,
    EvidenceState,
    ExpectedMetricTarget,
    InnovationPoint,
    ModuleIntent,
    PaperMethodCard,
    ProposalExpectedResult,
    ProposalExperiment,
    ProposalModule,
    ProposalReadiness,
    ProposalReference,
    ResultStatus,
    StrEnumDirection,
    StrongComparison,
    TailoredResearchProposal,
    TailoringDecision,
    TailoringTask,
    compose_tailored_research_proposal,
)

__all__ = [
    "PROPOSAL_POLICY_VERSION",
    "AcademicStory",
    "BaselineProposal",
    "BaselineReproduction",
    "EvidenceScope",
    "EvidenceState",
    "ExpectedMetricTarget",
    "InnovationPoint",
    "ModuleIntent",
    "PaperMethodCard",
    "ProposalExpectedResult",
    "ProposalExperiment",
    "ProposalModule",
    "ProposalReadiness",
    "ProposalReference",
    "ResultStatus",
    "StrEnumDirection",
    "StrongComparison",
    "TailoredResearchProposal",
    "TailoringDecision",
    "TailoringTask",
    "compose_tailored_research_proposal",
]
