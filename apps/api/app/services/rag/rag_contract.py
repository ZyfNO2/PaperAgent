"""Re6.6 RAG Contract — Citation-verified RAG answers.

RAGAnswerContract ensures every RAG answer cites specific chunks with
location verification. Citations must be traceable to source documents.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChunkCitation(BaseModel):
    """A specific chunk citation within a document."""
    chunk_id: str = ""
    document_id: str = ""
    page: int = 0
    paragraph: int = 0
    snippet: str = ""
    location_verified: bool = False


class ConflictReport(BaseModel):
    """Report of conflicting evidence between chunks."""
    chunk_id_a: str = ""
    chunk_id_b: str = ""
    description: str = ""


class RAGAnswerContract(BaseModel):
    """Citation-verified RAG answer.

    Every answer MUST cite at least one chunk. Answers without citations
    are rejected. Citations must have location_verified=True.
    """
    query: str = ""
    answer: str = ""
    cited_chunks: list[ChunkCitation] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "uncertain"] = "uncertain"
    conflicts: list[ConflictReport] = Field(default_factory=list)
    abstain_reason: str | None = None
    context_window_tokens: int = 0
    context_window_used: int = 0

    @model_validator(mode="after")
    def _validate_citations(self) -> "RAGAnswerContract":
        if not self.cited_chunks:
            if not self.abstain_reason:
                raise ValueError(
                    "RAG answer must have at least one cited chunk or "
                    "an explicit abstain_reason"
                )
        for chunk in self.cited_chunks:
            if not chunk.chunk_id:
                raise ValueError("every citation must have chunk_id")
            if not chunk.document_id:
                raise ValueError("every citation must have document_id")
        return self

    def has_verified_locations(self) -> bool:
        return all(c.location_verified for c in self.cited_chunks)

    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    def is_abstention(self) -> bool:
        return self.abstain_reason is not None


class CitationValidator:
    """Validates RAG citations against a chunk index."""

    def __init__(self, chunk_index: dict[str, dict] | None = None):
        self._chunk_index = chunk_index or {}

    def validate_chunk_exists(self, chunk_id: str) -> bool:
        return chunk_id in self._chunk_index

    def validate_document_exists(self, document_id: str) -> bool:
        return any(
            c.get("document_id") == document_id
            for c in self._chunk_index.values()
        )

    def validate_citation(self, citation: ChunkCitation) -> list[str]:
        """Validate a single citation. Returns list of issues."""
        issues: list[str] = []
        if not citation.chunk_id:
            issues.append("missing chunk_id")
        elif not self.validate_chunk_exists(citation.chunk_id):
            issues.append(f"chunk_id {citation.chunk_id} not found in index")
        if not citation.document_id:
            issues.append("missing document_id")
        elif not self.validate_document_exists(citation.document_id):
            issues.append(f"document_id {citation.document_id} not found in index")
        if not citation.location_verified:
            issues.append("location not verified")
        return issues

    def validate_answer(self, answer: RAGAnswerContract) -> tuple[bool, list[str]]:
        """Validate a complete RAG answer. Returns (passes, issues)."""
        issues: list[str] = []

        if answer.is_abstention():
            return True, []

        if not answer.cited_chunks:
            return False, ["no citations provided"]

        for i, chunk in enumerate(answer.cited_chunks):
            chunk_issues = self.validate_citation(chunk)
            for issue in chunk_issues:
                issues.append(f"citation[{i}]: {issue}")

        # Check for conflicts
        if answer.has_conflicts():
            for conflict in answer.conflicts:
                if not conflict.chunk_id_a or not conflict.chunk_id_b:
                    issues.append("conflict report missing chunk references")

        return len(issues) == 0, issues

    def detect_instruction_injection(self, answer: RAGAnswerContract) -> bool:
        """Detect if the answer contains potential prompt injection from ingested docs."""
        injection_patterns = [
            "ignore previous instructions",
            "system prompt:",
            "you are now",
            "forget all previous",
            "override:",
        ]
        text = answer.answer.lower() + answer.query.lower()
        return any(pattern in text for pattern in injection_patterns)
