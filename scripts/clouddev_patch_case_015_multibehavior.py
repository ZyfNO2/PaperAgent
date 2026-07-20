from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def _clean(value: str) -> str:
    return dedent(value).lstrip("\n")


def replace_once(path: Path, old: str, new: str) -> None:
    old_value = _clean(old)
    new_value = _clean(new)
    text = path.read_text(encoding="utf-8")
    if new_value in text:
        return
    count = text.count(old_value)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}")
    path.write_text(text.replace(old_value, new_value, 1), encoding="utf-8")


def insert_after(path: Path, anchor: str, addition: str) -> None:
    anchor_value = _clean(anchor)
    addition_value = _clean(addition)
    text = path.read_text(encoding="utf-8")
    if addition_value.strip() in text:
        return
    count = text.count(anchor_value)
    if count != 1:
        raise RuntimeError(f"{path}: expected one insertion anchor, found {count}")
    path.write_text(text.replace(anchor_value, anchor_value + addition_value, 1), encoding="utf-8")


def patch_query_overrides() -> None:
    path = Path("src/paperagent/literature/task_query_overrides.py")
    replace_once(
        path,
        '''
        _BASELINE_ROLE_HINTS = ("baseline", "comparison", "reproducible", "基线", "比较", "复现")
        ''',
        '''
        _MULTI_BEHAVIOR_RECOMMENDATION_HINTS = (
            "multi-behavior recommendation",
            "multi behavior recommendation",
            "multiple behavior recommendation",
            "multi-relational recommendation",
            "multi-action recommendation",
            "多行为推荐",
            "多行为推荐系统",
        )
        _RECOMMENDATION_RISK_HINTS = (
            "risk",
            "negative",
            "cold_start",
            "long_tail",
            "风险",
            "负面",
            "冷启动",
            "长尾",
        )
        _BASELINE_ROLE_HINTS = ("baseline", "comparison", "reproducible", "基线", "比较", "复现")
        ''',
    )
    replace_once(
        path,
        '''
            if _contains_any(combined, _TIME_SERIES_ANOMALY_HINTS):
        ''',
        '''
            if _contains_any(combined, _MULTI_BEHAVIOR_RECOMMENDATION_HINTS):
                role_text = f"{gap_id} {gap_description}".casefold()
                if role == "baseline":
                    canonical = "multi-behavior recommendation graph neural network"
                elif _contains_any(role_text, _RECOMMENDATION_RISK_HINTS):
                    canonical = "multi-behavior recommendation data sparsity cold-start long-tail"
                elif role == "mechanism":
                    canonical = "multi-behavior recommendation gated auxiliary behavior transfer"
                elif role == "parallel":
                    canonical = "multi-behavior recommendation contrastive learning"
                else:
                    canonical = "multi-behavior recommendation e-commerce"
                return _result(
                    query,
                    canonical,
                    "canonicalized multi-behavior recommendation retrieval by evidence role",
                )

            if _contains_any(combined, _TIME_SERIES_ANOMALY_HINTS):
        ''',
    )


def patch_specialized_guards() -> None:
    path = Path("src/paperagent/literature/specialized_guards.py")
    insert_after(
        path,
        '''
        _FEW_SHOT_CANDIDATE_TERMS = (
            "few-shot",
            "few shot",
            "zero-shot",
            "zero shot",
            "small sample",
            "low-resource",
            "low resource",
            "few labeled",
            "few examples",
            "meta-learning",
            "transfer learning",
        )
        ''',
        '''
        _MULTI_BEHAVIOR_RECOMMENDATION_QUERY_TERMS = (
            "multi-behavior recommendation",
            "multi behavior recommendation",
            "multiple behavior recommendation",
            "multi-relational recommendation",
            "multi-action recommendation",
            "多行为推荐",
        )
        _RECOMMENDATION_CANDIDATE_TERMS = (
            "recommendation",
            "recommender",
            "collaborative filtering",
            "user-item",
            "item recommendation",
            "ranking recommendation",
        )
        _MULTI_BEHAVIOR_CANDIDATE_TERMS = (
            "multi-behavior",
            "multi behavior",
            "multiple behavior",
            "multi-action",
            "multi action",
            "multi-relational",
            "auxiliary behavior",
            "behavior-aware",
            "behavior-specific",
            "heterogeneous behavior",
            "click and purchase",
            "view and purchase",
            "interaction types",
        )
        ''',
    )
    replace_once(
        path,
        '''
            few_shot_match = not (
                time_series_query and _contains_any(normalized_query, _FEW_SHOT_QUERY_TERMS)
            ) or _contains_any(normalized_candidate, _FEW_SHOT_CANDIDATE_TERMS)

            return (
        ''',
        '''
            few_shot_match = not (
                time_series_query and _contains_any(normalized_query, _FEW_SHOT_QUERY_TERMS)
            ) or _contains_any(normalized_candidate, _FEW_SHOT_CANDIDATE_TERMS)

            multi_behavior_query = _contains_any(
                normalized_query, _MULTI_BEHAVIOR_RECOMMENDATION_QUERY_TERMS
            )
            multi_behavior_match = not multi_behavior_query or (
                _contains_any(normalized_candidate, _RECOMMENDATION_CANDIDATE_TERMS)
                and _contains_any(normalized_candidate, _MULTI_BEHAVIOR_CANDIDATE_TERMS)
            )

            return (
        ''',
    )
    replace_once(
        path,
        '''
                and anomaly_transformer_match
                and few_shot_match
            )
        ''',
        '''
                and anomaly_transformer_match
                and few_shot_match
                and multi_behavior_match
            )
        ''',
    )


def patch_query_concepts() -> None:
    path = Path("src/paperagent/literature/query_concepts.py")
    replace_once(
        path,
        '''

        def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
        ''',
        '''
        _MULTI_BEHAVIOR_RECOMMENDATION_QUERY_HINTS = (
            "multi-behavior recommendation",
            "multi behavior recommendation",
            "multiple behavior recommendation",
            "multi-relational recommendation",
            "multi-action recommendation",
        )
        _RECOMMENDATION_CANDIDATE_TERMS = (
            "recommendation",
            "recommender",
            "collaborative filtering",
            "user-item",
            "item recommendation",
        )
        _MULTI_BEHAVIOR_CANDIDATE_TERMS = (
            "multi-behavior",
            "multi behavior",
            "multiple behavior",
            "multi-action",
            "multi action",
            "multi-relational",
            "auxiliary behavior",
            "behavior-aware",
            "behavior-specific",
            "heterogeneous behavior",
            "click and purchase",
            "view and purchase",
            "interaction types",
        )


        def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
        ''',
    )
    replace_once(
        path,
        '''
            if _contains_any(normalized, _INTENT_QUERY_HINTS):
                groups.append(_INTENT_CANDIDATE_TERMS)
                if _contains_any(normalized, _FEW_SHOT_QUERY_HINTS):
                    groups.append(_FEW_SHOT_CANDIDATE_TERMS)

            return tuple(groups)
        ''',
        '''
            if _contains_any(normalized, _INTENT_QUERY_HINTS):
                groups.append(_INTENT_CANDIDATE_TERMS)
                if _contains_any(normalized, _FEW_SHOT_QUERY_HINTS):
                    groups.append(_FEW_SHOT_CANDIDATE_TERMS)

            if _contains_any(normalized, _MULTI_BEHAVIOR_RECOMMENDATION_QUERY_HINTS):
                groups.extend(
                    (_RECOMMENDATION_CANDIDATE_TERMS, _MULTI_BEHAVIOR_CANDIDATE_TERMS)
                )

            return tuple(groups)
        ''',
    )


def patch_evidence_binding() -> None:
    path = Path("src/paperagent/evidence_gap_binding.py")
    replace_once(
        path,
        '''

        def _dedupe(values: Iterable[str]) -> list[str]:
        ''',
        '''
        _MULTI_BEHAVIOR_RECOMMENDATION_TASK_CUES = (
            "multi-behavior recommendation",
            "multi behavior recommendation",
            "multiple behavior recommendation",
            "multi-relational recommendation",
            "multi-action recommendation",
        )
        _RECOMMENDATION_TASK_CUES = (
            "recommendation",
            "recommender",
            "collaborative filtering",
            "user-item",
        )
        _MULTI_BEHAVIOR_EVIDENCE_CUES = (
            "multi-behavior",
            "multi behavior",
            "multiple behavior",
            "multi-action",
            "multi action",
            "multi-relational",
            "auxiliary behavior",
            "behavior-aware",
            "behavior-specific",
            "heterogeneous behavior",
            "click and purchase",
            "view and purchase",
            "interaction types",
        )


        def _is_multi_behavior_recommendation_evidence(text: str) -> bool:
            explicit_task = any(
                cue in text for cue in _MULTI_BEHAVIOR_RECOMMENDATION_TASK_CUES
            )
            paired_task = any(cue in text for cue in _RECOMMENDATION_TASK_CUES) and any(
                cue in text for cue in _MULTI_BEHAVIOR_EVIDENCE_CUES
            )
            return explicit_task or paired_task


        def _multi_behavior_recommendation_baseline_support(text: str) -> bool:
            if not _is_multi_behavior_recommendation_evidence(text):
                return False
            evaluation = any(
                cue in text
                for cue in (
                    "experiment",
                    "experimental",
                    "dataset",
                    "benchmark",
                    "evaluation",
                    "evaluate",
                    "result",
                    "performance",
                    "recall",
                    "ndcg",
                    "hit ratio",
                    "top-k",
                )
            )
            method_or_comparison = any(
                cue in text
                for cue in (
                    "we propose",
                    "we introduce",
                    "framework",
                    "network",
                    "model",
                    "graph convolution",
                    "graph neural",
                    "collaborative filtering",
                    "baseline",
                    "state-of-the-art",
                    "outperform",
                )
            )
            return evaluation and method_or_comparison


        def _multi_behavior_recommendation_mechanism_support(text: str) -> bool:
            if not _is_multi_behavior_recommendation_evidence(text):
                return False
            problem = any(
                cue in text
                for cue in (
                    "sparse",
                    "sparsity",
                    "noisy",
                    "noise",
                    "imbalance",
                    "heterogeneous",
                    "different semantics",
                    "behavior dependency",
                    "target behavior",
                    "auxiliary behavior",
                    "negative transfer",
                    "weak behavior",
                    "data scarcity",
                    "long-tail",
                    "cold-start",
                )
            )
            intervention = any(
                cue in text
                for cue in (
                    "gated",
                    "gate",
                    "graph convolution",
                    "graph neural",
                    "message passing",
                    "transfer",
                    "contrastive",
                    "multi-task",
                    "multitask",
                    "attention",
                    "behavior-specific",
                    "relation-specific",
                    "cascading",
                    "fusion",
                    "disentangle",
                )
            )
            return problem and intervention


        def _multi_behavior_recommendation_risk_support(text: str) -> bool:
            if not _is_multi_behavior_recommendation_evidence(text):
                return False
            return any(
                cue in text
                for cue in (
                    "cold-start",
                    "cold start",
                    "long-tail",
                    "long tail",
                    "sparsity",
                    "sparse",
                    "noisy auxiliary",
                    "negative transfer",
                    "target behavior degradation",
                    "popularity bias",
                    "behavior imbalance",
                    "chronological split",
                    "future interaction",
                    "target leakage",
                )
            )


        def _dedupe(values: Iterable[str]) -> list[str]:
        ''',
    )
    replace_once(
        path,
        '''
        def _baseline_role_support(text: str) -> bool:
            if _few_shot_intent_baseline_support(text):
                return True
        ''',
        '''
        def _baseline_role_support(text: str) -> bool:
            if _few_shot_intent_baseline_support(text):
                return True
            if _multi_behavior_recommendation_baseline_support(text):
                return True
        ''',
    )
    replace_once(
        path,
        '''
        def _mechanism_role_support(text: str) -> bool:
            if _few_shot_intent_mechanism_support(text):
                return True
        ''',
        '''
        def _mechanism_role_support(text: str) -> bool:
            if _few_shot_intent_mechanism_support(text):
                return True
            if _multi_behavior_recommendation_mechanism_support(text):
                return True
        ''',
    )
    replace_once(
        path,
        '''
        def _risk_role_support(text: str) -> bool:
            if _few_shot_intent_risk_support(text):
                return True
        ''',
        '''
        def _risk_role_support(text: str) -> bool:
            if _few_shot_intent_risk_support(text):
                return True
            if _multi_behavior_recommendation_risk_support(text):
                return True
        ''',
    )


def write_tests() -> None:
    Path("tests/literature/test_multibehavior_recommendation_precision.py").write_text(
        _clean(
            '''
            from __future__ import annotations

            import pytest

            from paperagent.literature.query_concepts import matches_required_candidate_terms
            from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
            from paperagent.literature.task_query_overrides import override_task_query


            @pytest.mark.parametrize(
                ("gap_id", "description", "expected"),
                [
                    (
                        "baseline_comparison",
                        "multi-behavior recommendation baseline comparison",
                        "multi-behavior recommendation graph neural network",
                    ),
                    (
                        "failure_mechanism",
                        "auxiliary behavior noise mechanism and gated transfer",
                        "multi-behavior recommendation gated auxiliary behavior transfer",
                    ),
                    (
                        "optional_risk",
                        "cold-start, long-tail, and negative evidence",
                        "multi-behavior recommendation data sparsity cold-start long-tail",
                    ),
                ],
            )
            def test_case_015_queries_are_canonicalized_by_role(
                gap_id: str, description: str, expected: str
            ) -> None:
                result = override_task_query(
                    "面向电商场景的多行为推荐系统基线方法数据集评估指标效率",
                    gap_id=gap_id,
                    gap_description=description,
                    research_context="面向电商场景的多行为推荐系统",
                )
                assert result.changed is True
                assert result.query == expected


            def test_multibehavior_recommendation_guard_accepts_task_matched_paper() -> None:
                query = "multi-behavior recommendation graph neural network"
                candidate = (
                    "A graph convolutional network for multi-behavior recommendation models "
                    "click, cart, and purchase interactions in an e-commerce recommender system."
                )
                assert matches_specialized_candidate_terms(query, candidate) is True
                assert matches_required_candidate_terms(query, candidate) is True


            @pytest.mark.parametrize(
                "candidate",
                [
                    "A multi-behavior virtual patient model simulates clinical treatment trajectories.",
                    "A graph neural network predicts molecular interactions for drug discovery.",
                    "A single-behavior recommender optimizes only purchase interactions.",
                ],
            )
            def test_multibehavior_recommendation_guard_rejects_cross_task_noise(
                candidate: str,
            ) -> None:
                query = "multi-behavior recommendation graph neural network"
                assert matches_specialized_candidate_terms(query, candidate) is False
                assert matches_required_candidate_terms(query, candidate) is False
            '''
        ),
        encoding="utf-8",
    )
    Path("tests/review/test_multibehavior_recommendation_binding.py").write_text(
        _clean(
            '''
            from __future__ import annotations

            from datetime import UTC, datetime

            from paperagent.evidence_gap_binding import build_evidence_ledger
            from paperagent.schemas import (
                EvidenceBundle,
                EvidenceGap,
                EvidenceItem,
                ResearchPlan,
                ResearchRequest,
            )
            from paperagent.schemas.plan import SearchQuery


            def _plan() -> ResearchPlan:
                gaps = [
                    EvidenceGap(
                        gap_id="baseline_comparison",
                        description="多行为推荐的可复现基线与强比较证据。",
                    ),
                    EvidenceGap(
                        gap_id="failure_mechanism",
                        description="辅助行为噪声、行为迁移机制与局限。",
                    ),
                    EvidenceGap(
                        gap_id="optional_risk",
                        description="冷启动、长尾、稀疏和负迁移风险。",
                        required=False,
                        minimum_accepted_items=0,
                    ),
                ]
                queries = [
                    SearchQuery(
                        query_id="q1",
                        gap_id="baseline_comparison",
                        query="multi-behavior recommendation graph neural network",
                        source_types=["paper"],
                    ),
                    SearchQuery(
                        query_id="q2",
                        gap_id="failure_mechanism",
                        query="multi-behavior recommendation gated auxiliary behavior transfer",
                        source_types=["paper"],
                    ),
                    SearchQuery(
                        query_id="q3",
                        gap_id="optional_risk",
                        query="multi-behavior recommendation data sparsity cold-start long-tail",
                        source_types=["paper"],
                    ),
                ]
                return ResearchPlan(
                    status="ready",
                    problem_statement="面向电商场景的多行为推荐系统",
                    scope="e-commerce multi-behavior recommendation for purchase ranking",
                    evidence_gaps=gaps,
                    search_queries=queries,
                    success_criteria=["找到任务匹配的基线、机制和风险证据"],
                    risks=["辅助行为噪声、冷启动、长尾和未来交互泄漏"],
                )


            def _item(
                *, evidence_id: str, gap_id: str, query: str, title: str, summary: str
            ) -> EvidenceItem:
                return EvidenceItem(
                    evidence_id=evidence_id,
                    source_type="paper",
                    title=title,
                    locator=f"doi:10.1000/{evidence_id}",
                    retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
                    verification_status="accepted",
                    supports_gap_ids=[gap_id],
                    summary=summary,
                    content_hash=f"sha256:{evidence_id}",
                    provider="literature_retrieval",
                    metadata={"candidate_gap_ids": gap_id, "query_text": query},
                )


            def _bundle(items: list[EvidenceItem]) -> EvidenceBundle:
                return EvidenceBundle(
                    items=items,
                    accepted_ids=[item.evidence_id for item in items],
                    identity_verified_ids=[item.evidence_id for item in items],
                    coverage_by_gap={item.supports_gap_ids[0]: 1 for item in items},
                )


            def test_case_015_evidence_binds_to_baseline_mechanism_and_risk_roles() -> None:
                items = [
                    _item(
                        evidence_id="ev-baseline",
                        gap_id="baseline_comparison",
                        query="multi-behavior recommendation graph neural network",
                        title="Multi-Behavior Recommendation with Graph Convolutional Networks",
                        summary=(
                            "We propose a graph neural network for multi-behavior recommendation "
                            "over click, cart, and purchase interactions. Experiments on two "
                            "e-commerce datasets report Recall and NDCG and outperform baselines."
                        ),
                    ),
                    _item(
                        evidence_id="ev-mechanism",
                        gap_id="failure_mechanism",
                        query="multi-behavior recommendation gated auxiliary behavior transfer",
                        title="Gated Behavior Transfer for Multi-Behavior Recommendation",
                        summary=(
                            "Auxiliary behaviors in a multi-behavior recommender are sparse, noisy, "
                            "and heterogeneous. We introduce gated behavior-specific transfer and "
                            "graph message passing to protect the target purchase behavior."
                        ),
                    ),
                    _item(
                        evidence_id="ev-risk",
                        gap_id="optional_risk",
                        query="multi-behavior recommendation data sparsity cold-start long-tail",
                        title="Robust Multi-Behavior Recommendation under Sparse Feedback",
                        summary=(
                            "Multi-behavior recommendation remains vulnerable to cold-start, "
                            "long-tail sparsity, behavior imbalance, and negative transfer from "
                            "noisy auxiliary behavior."
                        ),
                    ),
                ]
                _, _, _, supports, ledger = build_evidence_ledger(
                    request=ResearchRequest(question="面向电商场景的多行为推荐系统"),
                    plan=_plan(),
                    evidence=_bundle(items),
                )
                assert set(ledger.accepted_ids) == {"ev-baseline", "ev-mechanism", "ev-risk"}
                direct = {
                    (support.evidence_id, support.gap_id): support
                    for support in supports
                    if support.checklist_results.get("query_provenance_match")
                }
                assert direct[("ev-baseline", "baseline_comparison")].decision == "accept"
                assert direct[("ev-mechanism", "failure_mechanism")].decision == "accept"
                assert direct[("ev-risk", "optional_risk")].decision == "accept"
                for support in direct.values():
                    assert support.checklist_results["role_evidence_present"] is True
                    assert support.checklist_results["required_concepts_match"] is True


            def test_method_only_multibehavior_paper_without_evaluation_is_not_baseline() -> None:
                full_plan = _plan()
                plan = full_plan.model_copy(
                    update={
                        "evidence_gaps": [full_plan.evidence_gaps[0]],
                        "search_queries": [full_plan.search_queries[0]],
                    }
                )
                item = _item(
                    evidence_id="ev-no-eval",
                    gap_id="baseline_comparison",
                    query="multi-behavior recommendation graph neural network",
                    title="A Graph Network for Multi-Behavior Recommendation",
                    summary="We propose a graph network for multi-behavior recommendation.",
                )
                _, _, _, supports, ledger = build_evidence_ledger(
                    request=ResearchRequest(question="面向电商场景的多行为推荐系统"),
                    plan=plan,
                    evidence=_bundle([item]),
                )
                assert ledger.accepted_ids == []
                binding = next(
                    support for support in supports if support.gap_id == "baseline_comparison"
                )
                assert binding.checklist_results["role_evidence_present"] is False
            '''
        ),
        encoding="utf-8",
    )


def patch_workflows() -> None:
    for workflow in (
        Path(".github/workflows/second-batch-retrieval-offline-gate.yml"),
        Path(".github/workflows/claw-single-case-live-repair.yml"),
    ):
        insert_after(
            workflow,
            "            tests/literature/test_time_series_anomaly_precision.py\n",
            "            tests/literature/test_multibehavior_recommendation_precision.py\n",
        )
        insert_after(
            workflow,
            "            tests/review/test_few_shot_intent_role_binding.py\n",
            "            tests/review/test_multibehavior_recommendation_binding.py\n",
        )
        insert_after(
            workflow,
            "            tests/literature/test_time_series_anomaly_precision.py \\\n",
            "            tests/literature/test_multibehavior_recommendation_precision.py \\\n",
        )
        insert_after(
            workflow,
            "            tests/review/test_few_shot_intent_role_binding.py \\\n",
            "            tests/review/test_multibehavior_recommendation_binding.py \\\n",
        )

    batch = Path(".github/workflows/claw-four-case-live-batch.yml")
    insert_after(
        batch,
        "            tests/review/test_few_shot_intent_role_binding.py\n",
        "            tests/review/test_multibehavior_recommendation_binding.py\n",
    )
    insert_after(
        batch,
        "            tests/review/test_few_shot_intent_role_binding.py \\\n",
        "            tests/review/test_multibehavior_recommendation_binding.py \\\n",
    )
    insert_after(
        batch,
        "            tests/literature/test_query_concepts.py \\\n",
        "            tests/literature/test_multibehavior_recommendation_precision.py \\\n",
    )


def main() -> None:
    patch_query_overrides()
    patch_specialized_guards()
    patch_query_concepts()
    patch_evidence_binding()
    write_tests()
    patch_workflows()


if __name__ == "__main__":
    main()
