from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "Chinese long document classification hierarchical transformer",
            "A hierarchical transformer for long document classification aggregates chunk-level "
            "representations and is evaluated on Chinese documents.",
        ),
        (
            "long document classification truncation long context",
            "Long text classification suffers from truncation; a long-context encoder improves "
            "document categorization.",
        ),
        (
            "few-shot intent classification prototypical network",
            "A prototypical network for few-shot intent classification learns user-intent "
            "representations from five examples per class.",
        ),
        (
            "few-shot intent detection open set out-of-scope",
            "Few-shot intent detection with out-of-scope rejection evaluates unknown intents.",
        ),
    ],
)
def test_third_batch_guards_accept_task_matched_candidates(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "Chinese long document classification hierarchical transformer",
            "OpenCSG Chinese Corpus provides high-quality Chinese datasets for LLM training.",
        ),
        (
            "Chinese long document classification hierarchical transformer",
            "Benchmarking Chinese text recognition presents OCR datasets and recognition models.",
        ),
        (
            "long document classification truncation long context",
            "Long-range transformer architectures are studied for generic document understanding.",
        ),
        (
            "few-shot intent classification prototypical network",
            "Meta-Baseline explores simple meta-learning for few-shot image classification.",
        ),
        (
            "few-shot intent classification contrastive learning label semantics",
            "A top-related meta-learning method addresses few-shot object detection.",
        ),
        (
            "few-shot intent detection open set out-of-scope",
            "Few-shot learning with meta metric learners is evaluated on visual benchmarks.",
        ),
    ],
)
def test_third_batch_guards_reject_cross_task_false_positives(
    query: str, candidate: str
) -> None:
    assert matches_required_candidate_terms(query, candidate) is False


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_comparison",
            "baseline comparison and reproducibility",
            "Chinese long document classification hierarchical transformer",
        ),
        (
            "failure_mechanism",
            "failure mechanism and computational limitations",
            "long document classification truncation long context",
        ),
        (
            "data_optimization_methods",
            "parallel methods and data optimization alternatives",
            "long document classification hierarchical attention sparse transformer",
        ),
    ],
)
def test_long_document_queries_preserve_evidence_roles(
    gap_id: str, description: str, expected: str
) -> None:
    result = refine_search_query(
        "Chinese long document text classification models datasets efficiency",
        gap_id=gap_id,
        gap_description=description,
        research_context="中文长文本分类模型优化",
    )
    assert result.query == expected
    assert result.reason is not None
    assert "long-document classification" in result.reason


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_comparison",
            "baseline comparison",
            "few-shot intent classification prototypical network",
        ),
        (
            "mechanism_limitation",
            "mechanism, adaptation, and limitations",
            "few-shot intent classification contrastive learning label semantics",
        ),
        (
            "risk_negative_evidence",
            "risk and negative evidence for unknown intents",
            "few-shot intent detection open set out-of-scope",
        ),
    ],
)
def test_few_shot_intent_queries_preserve_evidence_roles(
    gap_id: str, description: str, expected: str
) -> None:
    result = refine_search_query(
        "few-shot text intention recognition industry-specific baseline",
        gap_id=gap_id,
        gap_description=description,
        research_context="小样本行业文本意图识别",
    )
    assert result.query == expected
    assert result.reason is not None
    assert "few-shot intent" in result.reason
