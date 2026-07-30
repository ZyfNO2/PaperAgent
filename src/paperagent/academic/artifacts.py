from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import Field, model_validator

from paperagent.academic.contracts import FrozenAcademicModel
from paperagent.academic.workflow import AcademicRAGWorkflow

AcademicArtifactType = Literal[
    "evidence_bundle",
    "paper_comparison",
    "baseline_card",
    "module_card",
    "compatibility_matrix",
    "experiment_matrix",
    "method_draft",
    "review_report",
]
AcademicArtifactState = Literal["draft", "approved", "rejected", "final"]


class EvidenceBoundClaim(FrozenAcademicModel):
    text: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()


class AcademicArtifactDraft(FrozenAcademicModel):
    artifact_type: AcademicArtifactType
    title: str
    project_id: str
    summary: str
    evidence_ids: tuple[str, ...]
    claims: tuple[EvidenceBoundClaim, ...]
    state: AcademicArtifactState = "draft"
    review_note: str | None = None

    @model_validator(mode="after")
    def validate_claim_bindings(self) -> AcademicArtifactDraft:
        allowed = set(self.evidence_ids)
        for claim in self.claims:
            if not set(claim.evidence_ids) <= allowed:
                raise ValueError("artifact claim references undeclared evidence")
        return self


class AcademicArtifactRevision(FrozenAcademicModel):
    artifact_id: str
    artifact_type: AcademicArtifactType
    revision_number: int = Field(ge=1)
    state: AcademicArtifactState
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AcademicTailoringArtifacts(FrozenAcademicModel):
    project_id: str
    decision: Literal["GO", "REVISE", "NO-GO", "BLOCKED"]
    reason_code: str
    revisions: tuple[AcademicArtifactRevision, ...]


@runtime_checkable
class AcademicArtifactSink(Protocol):
    def create_draft(self, draft: AcademicArtifactDraft) -> AcademicArtifactRevision: ...

    def review(
        self,
        artifact_id: str,
        *,
        decision: Literal["approved", "rejected"],
        note: str,
    ) -> AcademicArtifactRevision: ...

    def finalize(self, artifact_id: str) -> AcademicArtifactRevision: ...


class InMemoryAcademicArtifactSink:
    """Offline contract adapter; final product persistence belongs to PaperClaw."""

    def __init__(self) -> None:
        self._documents: dict[str, list[AcademicArtifactDraft]] = {}

    def create_draft(self, draft: AcademicArtifactDraft) -> AcademicArtifactRevision:
        if draft.state != "draft":
            raise ValueError("new artifact must be draft")
        artifact_id = f"academic-{uuid4().hex}"
        self._documents[artifact_id] = [draft]
        return self._revision(artifact_id)

    def review(
        self,
        artifact_id: str,
        *,
        decision: Literal["approved", "rejected"],
        note: str,
    ) -> AcademicArtifactRevision:
        current = self.read(artifact_id)
        if current.state == "final":
            raise ValueError("final artifact cannot be reviewed")
        if current.state != "draft":
            raise ValueError("only draft artifacts can be reviewed")
        clean_note = note.strip()
        if not clean_note:
            raise ValueError("review note must not be empty")
        self._documents[artifact_id].append(
            current.model_copy(update={"state": decision, "review_note": clean_note})
        )
        return self._revision(artifact_id)

    def finalize(self, artifact_id: str) -> AcademicArtifactRevision:
        current = self.read(artifact_id)
        if current.state != "approved":
            raise ValueError("final revision requires approved artifact")
        self._documents[artifact_id].append(current.model_copy(update={"state": "final"}))
        return self._revision(artifact_id)

    def read(self, artifact_id: str) -> AcademicArtifactDraft:
        try:
            return self._documents[artifact_id][-1]
        except KeyError as exc:
            raise KeyError(f"academic artifact not found: {artifact_id}") from exc

    def history(self, artifact_id: str) -> tuple[AcademicArtifactDraft, ...]:
        try:
            return tuple(self._documents[artifact_id])
        except KeyError as exc:
            raise KeyError(f"academic artifact not found: {artifact_id}") from exc

    def _revision(self, artifact_id: str) -> AcademicArtifactRevision:
        documents = self._documents[artifact_id]
        current = documents[-1]
        encoded = json.dumps(
            current.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return AcademicArtifactRevision(
            artifact_id=artifact_id,
            artifact_type=current.artifact_type,
            revision_number=len(documents),
            state=current.state,
            content_hash=hashlib.sha256(encoded).hexdigest(),
        )


class AcademicArtifactCoordinator:
    def __init__(
        self,
        rag: AcademicRAGWorkflow,
        sink: AcademicArtifactSink,
    ) -> None:
        self.rag = rag
        self.sink = sink

    def create_tailoring_drafts(
        self,
        *,
        project_id: str,
        hypothesis: str,
        baseline_paper_id: str,
        module_paper_ids: tuple[str, ...],
    ) -> AcademicTailoringArtifacts:
        clean_hypothesis = hypothesis.strip()
        if not clean_hypothesis:
            raise ValueError("hypothesis must not be empty")
        baseline = self.rag.run(
            project_id=project_id,
            question=f"Baseline evidence for: {clean_hypothesis}",
            paper_ids=(baseline_paper_id,),
        )
        modules = tuple(
            self.rag.run(
                project_id=project_id,
                question=f"Module evidence for: {clean_hypothesis}",
                paper_ids=(paper_id,),
            )
            for paper_id in module_paper_ids
        )
        if baseline.sufficiency in {"insufficient", "blocked"}:
            return AcademicTailoringArtifacts(
                project_id=project_id,
                decision="BLOCKED",
                reason_code="baseline_evidence_insufficient",
                revisions=(),
            )
        if not modules or any(
            result.sufficiency in {"insufficient", "blocked"} for result in modules
        ):
            return AcademicTailoringArtifacts(
                project_id=project_id,
                decision="BLOCKED",
                reason_code="module_evidence_insufficient",
                revisions=(),
            )
        baseline_ids = baseline.ledger.accepted_ids
        module_ids = tuple(
            evidence_id for result in modules for evidence_id in result.ledger.accepted_ids
        )
        all_ids = tuple(dict.fromkeys((*baseline_ids, *module_ids)))
        if not baseline_ids or not module_ids:
            return AcademicTailoringArtifacts(
                project_id=project_id,
                decision="BLOCKED",
                reason_code="accepted_evidence_missing",
                revisions=(),
            )
        drafts = self._drafts(
            project_id=project_id,
            hypothesis=clean_hypothesis,
            baseline_ids=baseline_ids,
            module_ids=module_ids,
            all_ids=all_ids,
        )
        return AcademicTailoringArtifacts(
            project_id=project_id,
            decision="REVISE",
            reason_code="compatibility_and_experiment_require_human_review",
            revisions=tuple(self.sink.create_draft(draft) for draft in drafts),
        )

    @staticmethod
    def _drafts(
        *,
        project_id: str,
        hypothesis: str,
        baseline_ids: tuple[str, ...],
        module_ids: tuple[str, ...],
        all_ids: tuple[str, ...],
    ) -> tuple[AcademicArtifactDraft, ...]:
        descriptions: tuple[tuple[AcademicArtifactType, str, str, tuple[str, ...]], ...] = (
            (
                "evidence_bundle",
                "Evidence Bundle",
                "Accepted baseline and module locators for the proposed study.",
                all_ids,
            ),
            (
                "paper_comparison",
                "Paper Comparison",
                "Evidence-scoped comparison draft; scientific differences require review.",
                all_ids,
            ),
            (
                "baseline_card",
                "Baseline Card",
                "Baseline identity and evidence draft.",
                baseline_ids,
            ),
            (
                "module_card",
                "Module Card",
                "Candidate module identity and evidence draft.",
                module_ids,
            ),
            (
                "compatibility_matrix",
                "Compatibility Matrix",
                "Compatibility remains unverified until code and tensor contracts are checked.",
                all_ids,
            ),
            (
                "experiment_matrix",
                "Experiment Matrix",
                "Proposed controlled experiments and ablations require human approval.",
                all_ids,
            ),
            (
                "method_draft",
                "Method Draft",
                f"Proposed hypothesis: {hypothesis}",
                all_ids,
            ),
            (
                "review_report",
                "Review Report",
                "Human review is required before any artifact becomes final.",
                all_ids,
            ),
        )
        return tuple(
            AcademicArtifactDraft(
                artifact_type=artifact_type,
                title=title,
                project_id=project_id,
                summary=summary,
                evidence_ids=evidence_ids,
                claims=(
                    EvidenceBoundClaim(
                        text=summary,
                        evidence_ids=evidence_ids,
                        limitations=("Draft claim; not a scientific GO decision.",),
                    ),
                ),
            )
            for artifact_type, title, summary, evidence_ids in descriptions
        )
