from __future__ import annotations

from pathlib import Path

import pytest

from paperagent.projects import (
    MemoryCategory,
    MemoryRAGWorkflow,
    MemoryScope,
    MemoryStatus,
    TailoringDecision,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_vertical_ingest_query_memory_restart_and_tailoring(tmp_path: Path) -> None:
    database = tmp_path / "paperagent.db"
    workflow = MemoryRAGWorkflow(database)
    project = workflow.create_project(
        name="ResNet ECA Mixup",
        research_question="Can channel attention and mixup improve ResNet robustness?",
    )
    resnet = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="resnet",
        title="Deep Residual Learning for Image Recognition",
        path=_write(
            tmp_path / "resnet.md",
            """# Deep Residual Learning for Image Recognition

## Method
Residual learning reformulates layers as learning residual functions with reference
to the layer inputs.

Identity shortcut connections add neither extra parameters nor computational complexity.

## Experiments
The network is evaluated on ImageNet and CIFAR-10 using top-1 and top-5 classification error.
""",
        ),
    )
    eca = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="eca",
        title="ECA-Net: Efficient Channel Attention",
        path=_write(
            tmp_path / "eca.md",
            """# ECA-Net

## Method
Efficient channel attention avoids dimensionality reduction and captures local
cross-channel interaction through a fast one-dimensional convolution.

## Complexity
The module adds very few parameters while improving image classification accuracy.
""",
        ),
    )
    mixup = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="mixup",
        title="mixup: Beyond Empirical Risk Minimization",
        path=_write(
            tmp_path / "mixup.md",
            """# mixup

## Training
Mixup trains a neural network on convex combinations of pairs of examples and their labels.

This regularization encourages linear behavior between training examples.

## Evaluation
The method improves generalization and robustness to corrupted labels on image classification tasks.
""",
        ),
    )

    hits = workflow.query(
        project_id=project.project_id,
        query="channel attention robustness classification",
        limit=8,
    )
    assert {hit.unit.paper_id for hit in hits} >= {"eca", "mixup"}
    assert all(hit.unit.locator.quote for hit in hits)

    proposal = workflow.propose_memory(
        project_id=project.project_id,
        scope=MemoryScope.LONG_TERM,
        category=MemoryCategory.DECISION,
        content="Use ResNet as the frozen baseline and evaluate ECA and mixup separately first.",
        evidence_unit_ids=(
            resnet.evidence_units[0].unit_id,
            eca.evidence_units[0].unit_id,
            mixup.evidence_units[0].unit_id,
        ),
    )
    assert proposal.status is MemoryStatus.PROPOSED
    assert workflow.repository.list_memory(project.project_id) == ()

    approved = workflow.review_memory(
        proposal.memory_id,
        approve=True,
        note="Approved after checking the cited paper units.",
    )
    assert approved.status is MemoryStatus.APPROVED

    restarted = MemoryRAGWorkflow(database)
    memory = restarted.repository.list_memory(project.project_id)
    assert [entry.content for entry in memory] == [proposal.content]
    assert len(restarted.repository.list_latest_papers(project.project_id)) == 3

    plan = restarted.design_tailoring_plan(
        project_id=project.project_id,
        baseline_paper_id="resnet",
        module_paper_ids=("eca", "mixup"),
        hypothesis=(
            "Adding efficient channel attention and mixup should improve classification robustness "
            "without changing the residual backbone contract."
        ),
        evidence_query="classification robustness attention residual training",
    )
    assert plan.decision is TailoringDecision.REVISE
    assert plan.reason_code == "compatibility_contract_not_independently_verified"
    assert {module.paper_id for module in plan.modules} == {"eca", "mixup"}
    assert len(plan.citations) >= 3


def test_tailoring_blocks_without_independent_module_evidence(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "paperagent.db")
    project = workflow.create_project(name="Baseline only", research_question="Test")
    workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="resnet",
        title="ResNet",
        path=_write(
            tmp_path / "resnet.txt",
            "Residual learning supports image classification experiments.",
        ),
    )
    plan = workflow.design_tailoring_plan(
        project_id=project.project_id,
        baseline_paper_id="resnet",
        module_paper_ids=(),
        hypothesis="Improve image classification",
    )
    assert plan.decision is TailoringDecision.BLOCKED
    assert plan.reason_code == "module_design_deferred:insufficient_independent_evidence"


def test_ingestion_versions_replace_search_view_but_preserve_history(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "paperagent.db")
    project = workflow.create_project(name="Versioning", research_question="Track updates")
    source = _write(tmp_path / "paper.md", "# Paper\n\nOriginal residual method description.")
    first = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="paper-a",
        path=source,
        title="Paper A",
    )
    source.write_text("# Paper\n\nUpdated attention mechanism description.", encoding="utf-8")
    second = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="paper-a",
        path=source,
        title="Paper A",
    )
    assert first.paper.ingestion_version == 1
    assert second.paper.ingestion_version == 2
    units = workflow.repository.list_evidence_units(project.project_id)
    assert {unit.ingestion_version for unit in units} == {2}
    assert any("Updated" in unit.content for unit in units)


def test_memory_gate_rejects_unknown_evidence_and_double_review(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "paperagent.db")
    project = workflow.create_project(name="Memory gates", research_question="Gate writes")
    with pytest.raises(ValueError, match="unknown evidence"):
        workflow.propose_memory(
            project_id=project.project_id,
            scope=MemoryScope.WORKING,
            category=MemoryCategory.FINDING,
            content="Unsupported memory",
            evidence_unit_ids=("missing",),
        )
    proposal = workflow.propose_memory(
        project_id=project.project_id,
        scope=MemoryScope.WORKING,
        category=MemoryCategory.NEXT_ACTION,
        content="Ingest the baseline paper.",
    )
    workflow.review_memory(proposal.memory_id, approve=False)
    with pytest.raises(ValueError, match="only proposed"):
        workflow.review_memory(proposal.memory_id, approve=True)
