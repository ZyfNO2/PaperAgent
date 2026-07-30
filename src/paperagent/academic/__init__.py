from paperagent.academic.artifacts import (
    AcademicArtifactCoordinator,
    AcademicArtifactDraft,
    AcademicArtifactRevision,
    AcademicArtifactSink,
    AcademicTailoringArtifacts,
    EvidenceBoundClaim,
    InMemoryAcademicArtifactSink,
)
from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicEvidenceEntry,
    AcademicEvidenceLedger,
    AcademicEvidenceSource,
    AcademicLocator,
    AcademicQueryPlan,
    AcademicRAGResult,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
)
from paperagent.academic.project_adapter import ProjectRAGEvidenceSource
from paperagent.academic.workflow import AcademicRAGWorkflow

__all__ = [
    "AcademicArtifactCoordinator",
    "AcademicArtifactDraft",
    "AcademicArtifactRevision",
    "AcademicArtifactSink",
    "AcademicCandidate",
    "AcademicEvidenceEntry",
    "AcademicEvidenceLedger",
    "AcademicEvidenceSource",
    "AcademicLocator",
    "AcademicQueryPlan",
    "AcademicRAGResult",
    "AcademicRAGWorkflow",
    "AcademicRetrievalRequest",
    "AcademicRetrievalResult",
    "AcademicTailoringArtifacts",
    "EvidenceBoundClaim",
    "InMemoryAcademicArtifactSink",
    "ProjectRAGEvidenceSource",
]
