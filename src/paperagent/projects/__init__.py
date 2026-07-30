from typing import TYPE_CHECKING, Any

from paperagent.projects.ingestion import PaperIngestionService
from paperagent.projects.models import (
    CitationLocator,
    EvidenceUnit,
    IngestionResult,
    MemoryCategory,
    MemoryScope,
    MemoryStatus,
    PaperVersion,
    ProjectMemoryEntry,
    ResearchProject,
    SearchHit,
    TailoringDecision,
    TailoringModule,
    TailoringPlan,
)
from paperagent.projects.rag import HybridAcademicRetriever
from paperagent.projects.repository import (
    MemoryEntryNotFoundError,
    PaperNotFoundError,
    ProjectNotFoundError,
    SQLiteProjectRepository,
)
from paperagent.projects.tailoring import EvidenceBoundTailoringService

if TYPE_CHECKING:
    from paperagent.projects.workflow import MemoryRAGWorkflow

__all__ = [
    "CitationLocator",
    "EvidenceBoundTailoringService",
    "EvidenceUnit",
    "HybridAcademicRetriever",
    "IngestionResult",
    "MemoryCategory",
    "MemoryEntryNotFoundError",
    "MemoryRAGWorkflow",
    "MemoryScope",
    "MemoryStatus",
    "PaperIngestionService",
    "PaperNotFoundError",
    "PaperVersion",
    "ProjectMemoryEntry",
    "ProjectNotFoundError",
    "ResearchProject",
    "SQLiteProjectRepository",
    "SearchHit",
    "TailoringDecision",
    "TailoringModule",
    "TailoringPlan",
]


def __getattr__(name: str) -> Any:
    if name == "MemoryRAGWorkflow":
        from paperagent.projects.workflow import MemoryRAGWorkflow

        return MemoryRAGWorkflow
    raise AttributeError(name)
