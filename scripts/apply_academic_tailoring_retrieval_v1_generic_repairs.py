from __future__ import annotations

from pathlib import Path


EVIDENCE_PATH = Path("src/paperagent/evidence_gap_binding.py")
PLANNING_PATH = Path("src/paperagent/nodes/planning.py")
SEMANTIC_TEST_PATH = Path("tests/review/test_semantic_gap_binding.py")
PLANNING_TEST_PATH = Path("tests/nodes/test_intake_planning.py")


def _patch_evidence_binding() -> None:
    source = EVIDENCE_PATH.read_text(encoding="utf-8")
    result_marker = '''_RESULT_CUES = (
    "reports",
    "reported",
    "achieves",
    "achieved",
    "measured",
    "result",
    "outperform",
    "improvement",
    "degradation",
    "报告",
    "达到",
    "结果",
    "提升",
    "下降",
)
'''
    result_replacement = result_marker + '''_COMPARATIVE_EXPERIMENT_CUES = (
    "experimental results",
    "experiments demonstrate",
    "experiments show",
    "extensive experiments",
    "evaluation demonstrates",
    "outperforms",
    "outperformed",
    "superiority",
    "competitive performance",
    "实验结果",
    "实验证明",
    "大量实验",
    "优于",
    "具有竞争力",
)
'''
    if "_COMPARATIVE_EXPERIMENT_CUES" not in source:
        if result_marker not in source:
            raise RuntimeError("result cue insertion marker not found")
        source = source.replace(result_marker, result_replacement, 1)

    old = '''def _baseline_role_support(item: EvidenceItem, text: str) -> bool:
    concrete_method = _has_concrete_method_identity(item)
    evaluation_setting = any(cue in text for cue in _EVALUATION_CUES)
    measured_result = bool(_METRIC_PATTERN.search(text)) and (
        bool(_NUMBER_PATTERN.search(text)) or any(cue in text for cue in _RESULT_CUES)
    )
    return concrete_method and evaluation_setting and measured_result
'''
    new = '''def _baseline_role_support(item: EvidenceItem, text: str) -> bool:
    concrete_method = _has_concrete_method_identity(item)
    evaluation_setting = any(cue in text for cue in _EVALUATION_CUES)
    explicit_metric_result = bool(_METRIC_PATTERN.search(text)) and (
        bool(_NUMBER_PATTERN.search(text)) or any(cue in text for cue in _RESULT_CUES)
    )
    comparative_experiment = evaluation_setting and any(
        cue in text for cue in _COMPARATIVE_EXPERIMENT_CUES
    )
    return concrete_method and evaluation_setting and (
        explicit_metric_result or comparative_experiment
    )
'''
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError("baseline role support block not found")
    EVIDENCE_PATH.write_text(source, encoding="utf-8")


def _patch_planning() -> None:
    source = PLANNING_PATH.read_text(encoding="utf-8")
    old_identity = '''        query_id = _unique_identifier(identity.query_id, existing_query_ids)
        identity_gaps.append(
            EvidenceGap(
                gap_id=gap_id,
                description=(
                    "Verify the public identity, method details, declared role, and task "
                    f"compatibility of the user-supplied material titled {identity.title!r}."
                ),
                required=True,
                minimum_accepted_items=1,
            )
        )
        identity_queries.append(
            SearchQuery(
                query_id=query_id,
                gap_id=gap_id,
                query=identity.title,
                source_types=["paper", "repository", "web"],
            )
        )
        available_slots -= 1
'''
    new_identity = '''        query_id = _unique_identifier(identity.query_id, existing_query_ids)
        exact_title = identity.title.replace('"', " ").strip()
        identity_gaps.append(
            EvidenceGap(
                gap_id=gap_id,
                description=(
                    "Verify the public identity, method details, declared role, and task "
                    f"compatibility of the user-supplied material titled {identity.title!r}."
                ),
                required=True,
                minimum_accepted_items=1,
            )
        )
        identity_queries.append(
            SearchQuery(
                query_id=query_id,
                gap_id=gap_id,
                query=f'"{exact_title}"',
                source_types=["paper", "web"],
            )
        )
        available_slots -= 1
        if available_slots <= 0:
            continue
        repository_query_id = _unique_identifier(
            f"{identity.query_id}-implementation", existing_query_ids
        )
        identity_queries.append(
            SearchQuery(
                query_id=repository_query_id,
                gap_id=gap_id,
                query=f'"{exact_title}" official implementation code repository',
                source_types=["repository", "web"],
            )
        )
        available_slots -= 1
'''
    if old_identity in source:
        source = source.replace(old_identity, new_identity, 1)
    elif "official implementation code repository" not in source:
        raise RuntimeError("user material identity query block not found")

    helper = '''

def _ensure_public_asset_discovery_query(
    plan: ResearchPlan,
    *,
    query_budget: int,
) -> ResearchPlan:
    """Add one generic code/data discovery lane when the plan omitted public assets."""

    if plan.status == "blocked" or not plan.evidence_gaps:
        return plan
    if len(plan.search_queries) >= query_budget:
        return plan
    if any("repository" in query.source_types for query in plan.search_queries):
        return plan
    target_gap = next(
        (gap for gap in plan.evidence_gaps if gap.required),
        plan.evidence_gaps[0],
    )
    existing_query_ids = {query.query_id for query in plan.search_queries}
    query_id = _unique_identifier("public-asset-discovery", existing_query_ids)
    asset_query = SearchQuery(
        query_id=query_id,
        gap_id=target_gap.gap_id,
        query=f"{plan.problem_statement} official implementation repository public dataset",
        source_types=["repository", "dataset", "web"],
    )
    return plan.model_copy(update={"search_queries": [*plan.search_queries, asset_query]})
'''
    marker = "\n\nasync def planning_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:\n"
    if "def _ensure_public_asset_discovery_query(" not in source:
        if marker not in source:
            raise RuntimeError("planning node insertion marker not found")
        source = source.replace(marker, helper + marker, 1)

    old_result = '''    if result is not None:
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_materials)
'''
    new_result = '''    if result is not None:
        with_materials = _ensure_user_material_identity_queries(
            result,
            request,
            query_budget=query_budget,
        )
        with_assets = _ensure_public_asset_discovery_query(
            with_materials,
            query_budget=query_budget,
        )
        patch["plan"] = _normalize_nonblocking_clarification(with_assets)
'''
    if old_result in source:
        source = source.replace(old_result, new_result, 1)
    elif new_result not in source:
        raise RuntimeError("planning result normalization block not found")
    PLANNING_PATH.write_text(source, encoding="utf-8")


def _append_tests() -> None:
    semantic_tests = SEMANTIC_TEST_PATH.read_text(encoding="utf-8")
    semantic_addition = r'''


def _cold_start_plan() -> ResearchPlan:
    gap = EvidenceGap(
        gap_id="cold_start_baseline",
        description="寻找冷启动序列推荐的具体基线、公开数据集、实验设置和对比证据。",
    )
    return ResearchPlan(
        status="ready",
        problem_statement="带内容信息的冷启动序列推荐",
        scope="新物品与短历史用户的序列推荐",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q_cold_start",
                gap_id=gap.gap_id,
                query=(
                    "cold-start sequential recommendation content features "
                    "public dataset baseline comparison"
                ),
                source_types=["paper"],
            )
        ],
        success_criteria=["找到有公开实验设置的具体方法"],
        risks=["摘要可能不包含具体数值"],
    )


def test_comparative_experiment_without_numeric_metric_supports_baseline_role() -> None:
    plan = _cold_start_plan()
    gap_id = plan.evidence_gaps[0].gap_id
    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="带内容信息的冷启动序列推荐"),
        plan=plan,
        evidence=_bundle(
            title="Recformer: Text Representations for Sequential Recommendation",
            summary=(
                "We introduce a content-aware sequential recommendation architecture. "
                "Extensive experiments on six public datasets demonstrate superiority "
                "for cold-start sequential recommendation with item content features."
            ),
            candidate_gap_id=gap_id,
        ),
    )

    assert ledger.accepted_ids == ["ev-paper"]
    binding = next(item for item in support if item.gap_id == gap_id)
    assert binding.decision == "accept"
    assert binding.checklist_results["role_evidence_present"] is True


def test_generic_survey_without_method_identity_remains_rejected() -> None:
    plan = _cold_start_plan()
    gap_id = plan.evidence_gaps[0].gap_id
    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="带内容信息的冷启动序列推荐"),
        plan=plan,
        evidence=_bundle(
            title="A Survey on Sequential Recommendation",
            summary=(
                "This survey reviews cold-start sequential recommendation, public datasets, "
                "content features, and common experimental comparisons."
            ),
            candidate_gap_id=gap_id,
        ),
    )

    assert ledger.accepted_ids == []
    binding = next(item for item in support if item.gap_id == gap_id)
    assert binding.decision == "reject"
    assert binding.checklist_results["role_evidence_present"] is False
'''
    if "test_comparative_experiment_without_numeric_metric_supports_baseline_role" not in semantic_tests:
        semantic_tests += semantic_addition
    SEMANTIC_TEST_PATH.write_text(semantic_tests, encoding="utf-8")

    planning_tests = PLANNING_TEST_PATH.read_text(encoding="utf-8")
    planning_addition = r'''


def test_user_material_identity_queries_add_exact_paper_and_repository_lanes() -> None:
    from paperagent.nodes.planning import _ensure_user_material_identity_queries
    from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="verify supplied baseline",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="baseline evidence")],
        search_queries=[SearchQuery(query_id="q1", gap_id="g1", query="task evidence")],
    )
    request = ResearchRequest(
        question="verify supplied baseline",
        user_material_refs=["A Concrete Method [declared role: baseline]"],
    )

    updated = _ensure_user_material_identity_queries(plan, request, query_budget=10)
    identity_gap_ids = {
        gap.gap_id for gap in updated.evidence_gaps if gap.gap_id.startswith("user-material")
    }
    identity_queries = [
        query for query in updated.search_queries if query.gap_id in identity_gap_ids
    ]

    assert [query.query for query in identity_queries] == [
        '"A Concrete Method"',
        '"A Concrete Method" official implementation code repository',
    ]
    assert identity_queries[0].source_types == ["paper", "web"]
    assert identity_queries[1].source_types == ["repository", "web"]


def test_public_asset_discovery_adds_one_generic_code_and_data_lane() -> None:
    from paperagent.nodes.planning import _ensure_public_asset_discovery_query
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="few-shot scientific classification",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="find a task baseline")],
        search_queries=[
            SearchQuery(query_id="q1", gap_id="g1", query="classification baseline paper")
        ],
    )

    updated = _ensure_public_asset_discovery_query(plan, query_budget=10)
    asset_queries = [
        query for query in updated.search_queries if query.query_id.startswith("public-asset-discovery")
    ]

    assert len(asset_queries) == 1
    assert asset_queries[0].gap_id == "g1"
    assert asset_queries[0].source_types == ["repository", "dataset", "web"]
    assert "official implementation repository public dataset" in asset_queries[0].query
'''
    if "test_user_material_identity_queries_add_exact_paper_and_repository_lanes" not in planning_tests:
        planning_tests += planning_addition
    PLANNING_TEST_PATH.write_text(planning_tests, encoding="utf-8")


def main() -> int:
    _patch_evidence_binding()
    _patch_planning()
    _append_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
