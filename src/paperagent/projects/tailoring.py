from __future__ import annotations

from collections.abc import Iterable

from paperagent.projects.models import (
    TailoringDecision,
    TailoringModule,
    TailoringPlan,
)
from paperagent.projects.rag import HybridAcademicRetriever
from paperagent.projects.repository import PaperNotFoundError, SQLiteProjectRepository


class EvidenceBoundTailoringService:
    def __init__(
        self,
        repository: SQLiteProjectRepository,
        retriever: HybridAcademicRetriever | None = None,
    ) -> None:
        self.repository = repository
        self.retriever = retriever or HybridAcademicRetriever(repository)

    def design(
        self,
        *,
        project_id: str,
        hypothesis: str,
        baseline_paper_id: str,
        module_paper_ids: Iterable[str],
        evidence_query: str | None = None,
    ) -> TailoringPlan:
        clean_hypothesis = hypothesis.strip()
        if not clean_hypothesis:
            raise ValueError("hypothesis must not be empty")
        module_ids = tuple(
            paper_id
            for paper_id in dict.fromkeys(module_paper_ids)
            if paper_id != baseline_paper_id
        )
        try:
            baseline = self.repository.get_latest_paper(
                project_id=project_id, paper_id=baseline_paper_id
            )
        except PaperNotFoundError:
            return TailoringPlan(
                project_id=project_id,
                decision=TailoringDecision.BLOCKED,
                reason_code="baseline_identity_missing",
                hypothesis=clean_hypothesis,
                risks=("The declared baseline is not present in the project corpus.",),
            )

        query = (evidence_query or clean_hypothesis).strip()
        baseline_hits = self.retriever.search(
            project_id=project_id,
            query=query,
            limit=4,
            paper_ids=(baseline_paper_id,),
        )
        if not baseline_hits:
            return TailoringPlan(
                project_id=project_id,
                decision=TailoringDecision.BLOCKED,
                reason_code="baseline_evidence_missing",
                baseline_paper_id=baseline_paper_id,
                hypothesis=clean_hypothesis,
                risks=(
                    "The baseline exists but no supporting evidence unit matched the hypothesis.",
                ),
            )
        if not module_ids:
            return TailoringPlan(
                project_id=project_id,
                decision=TailoringDecision.BLOCKED,
                reason_code="module_design_deferred:insufficient_independent_evidence",
                baseline_paper_id=baseline_paper_id,
                baseline_evidence_unit_ids=tuple(hit.unit.unit_id for hit in baseline_hits),
                hypothesis=clean_hypothesis,
                citations=tuple(hit.unit.locator for hit in baseline_hits),
                risks=("At least one independently ingested module paper is required.",),
            )

        modules: list[TailoringModule] = []
        citations = [hit.unit.locator for hit in baseline_hits]
        risks: list[str] = [
            "Compatibility is proposed from textual evidence only; tensor semantics, "
            "gradients, loss scale, license, and compute still require implementation checks."
        ]
        for module_id in module_ids:
            try:
                module_paper = self.repository.get_latest_paper(
                    project_id=project_id, paper_id=module_id
                )
            except PaperNotFoundError:
                return TailoringPlan(
                    project_id=project_id,
                    decision=TailoringDecision.BLOCKED,
                    reason_code="parallel_module_identity_missing",
                    baseline_paper_id=baseline_paper_id,
                    baseline_evidence_unit_ids=tuple(hit.unit.unit_id for hit in baseline_hits),
                    hypothesis=clean_hypothesis,
                    citations=tuple(citations),
                    risks=(f"Module paper {module_id} is not present in the project corpus.",),
                )
            module_hits = self.retriever.search(
                project_id=project_id,
                query=query,
                limit=4,
                paper_ids=(module_id,),
            )
            if not module_hits:
                return TailoringPlan(
                    project_id=project_id,
                    decision=TailoringDecision.BLOCKED,
                    reason_code="module_design_deferred:insufficient_independent_evidence",
                    baseline_paper_id=baseline_paper_id,
                    baseline_evidence_unit_ids=tuple(hit.unit.unit_id for hit in baseline_hits),
                    hypothesis=clean_hypothesis,
                    citations=tuple(citations),
                    risks=(
                        (
                            f"Module paper {module_paper.title} has no matching evidence "
                            "for the hypothesis."
                        ),
                    ),
                )
            citations.extend(hit.unit.locator for hit in module_hits)
            modules.append(
                TailoringModule(
                    paper_id=module_id,
                    paper_title=module_paper.title,
                    evidence_unit_ids=tuple(hit.unit.unit_id for hit in module_hits),
                    proposed_role=(
                        "Proposed intervention supported by project-corpus evidence; "
                        "integration contract remains to be verified in code."
                    ),
                    status="proposed",
                )
            )
        return TailoringPlan(
            project_id=project_id,
            decision=TailoringDecision.REVISE,
            reason_code="compatibility_contract_not_independently_verified",
            baseline_paper_id=baseline.paper_id,
            baseline_evidence_unit_ids=tuple(hit.unit.unit_id for hit in baseline_hits),
            hypothesis=clean_hypothesis,
            modules=tuple(modules),
            citations=tuple(citations),
            risks=tuple(risks),
        )
