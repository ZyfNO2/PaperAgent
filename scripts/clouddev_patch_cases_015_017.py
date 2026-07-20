from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "src/paperagent/claw_benchmark_adapter.py"
TESTS = ROOT / "tests/evals/test_claw_benchmark_adapter.py"


def patch_adapter() -> None:
    text = ADAPTER.read_text(encoding="utf-8")
    if "import hashlib\nimport re\n" not in text:
        text = text.replace(
            "from __future__ import annotations\n\nfrom collections.abc import Iterable\n",
            "from __future__ import annotations\n\nimport hashlib\nimport re\nfrom collections.abc import Iterable\n",
            1,
        )

    if "request = state.get(\"request\")" not in text.split("def _fact_partitions", 1)[1].split(
        "def _gap_roles", 1
    )[0]:
        old = '''def _fact_partitions(state: PaperAgentState) -> FactPartitions:
    synthesis = state.get("synthesis")
    report = state.get("report")
    method = state.get("method")
    plan = state.get("plan")
    contract = state.get("research_contract")
    outcome = state.get("final_outcome")

    verified = (
        _dedupe(item.text for item in synthesis.verified_findings) if synthesis is not None else ()
    )
    inferred = _dedupe(item.text for item in report.inferred_findings) if report is not None else ()
    proposed = _dedupe(
        (
            method.problem_method_insight if method is not None else None,
            method.falsifiable_hypothesis if method is not None else None,
            report.proposed_method if report is not None else None,
        )
    )
    unknown = _dedupe(
        (
            *(plan.risks if plan is not None else []),
            plan.clarification_question if plan is not None else None,
            *(contract.assumptions if contract is not None else []),
            *(contract.unavailable_private_evidence if contract is not None else []),
            *(outcome.missing_gap_ids if outcome is not None else []),
        )
    )

    used = set(verified)
    inferred = tuple(item for item in inferred if item not in used)
    used.update(inferred)
    proposed = tuple(item for item in proposed if item not in used)
    used.update(proposed)
    unknown = tuple(item for item in unknown if item not in used)
    return FactPartitions(
        verified=verified,
        inferred=inferred,
        proposed=proposed,
        unknown=unknown,
    )
'''
        new = '''def _fact_partitions(state: PaperAgentState) -> FactPartitions:
    synthesis = state.get("synthesis")
    report = state.get("report")
    method = state.get("method")
    plan = state.get("plan")
    request = state.get("request")
    contract = state.get("research_contract")
    outcome = state.get("final_outcome")

    verified = (
        _dedupe(item.text for item in synthesis.verified_findings) if synthesis is not None else ()
    )
    inferred = _dedupe(item.text for item in report.inferred_findings) if report is not None else ()
    proposed = _dedupe(
        (
            method.problem_method_insight if method is not None else None,
            method.falsifiable_hypothesis if method is not None else None,
            report.proposed_method if report is not None else None,
        )
    )
    if not verified and not inferred and not proposed:
        inferred = _dedupe(
            (
                plan.problem_statement if plan is not None else None,
                plan.scope if plan is not None else None,
            )
        )
    if not verified and not inferred and not proposed and request is not None:
        verified = _dedupe((f"User-declared research objective: {request.question}",))
    unknown = _dedupe(
        (
            *(plan.risks if plan is not None else []),
            plan.clarification_question if plan is not None else None,
            *(contract.assumptions if contract is not None else []),
            *(contract.unavailable_private_evidence if contract is not None else []),
            *(outcome.missing_gap_ids if outcome is not None else []),
        )
    )

    used = set(verified)
    inferred = tuple(item for item in inferred if item not in used)
    used.update(inferred)
    proposed = tuple(item for item in proposed if item not in used)
    used.update(proposed)
    unknown = tuple(item for item in unknown if item not in used)
    return FactPartitions(
        verified=verified,
        inferred=inferred,
        proposed=proposed,
        unknown=unknown,
    )
'''
        if old not in text:
            raise RuntimeError("fact partition block not found")
        text = text.replace(old, new, 1)

    if "def _roles_from_text" not in text:
        old = '''def _role_from_text(value: str) -> EvidenceRole:
    text = value.casefold()
    if any(token in text for token in ("baseline", "基线", "reproduction")):
        return "baseline"
    if any(token in text for token in ("strong comparison", "sota", "comparison", "对比")):
        return "strong_comparison"
    if any(token in text for token in ("risk", "failure", "negative", "风险", "失败")):
        return "risk"
    if any(token in text for token in ("parallel", "module", "mechanism", "平行", "模块", "机制")):
        return "parallel_method"
    if any(token in text for token in ("gap", "limitation", "problem", "缺口", "局限")):
        return "gap"
    return "other"
'''
        new = '''def _roles_from_text(value: str) -> tuple[EvidenceRole, ...]:
    text = value.casefold()
    roles: list[EvidenceRole] = []
    if any(token in text for token in ("baseline", "基线", "reproduction", "复现")):
        roles.append("baseline")
    if any(
        token in text
        for token in (
            "strong comparison",
            "strong comparative",
            "sota",
            "comparison",
            "强比较",
            "强对比",
            "对比方法",
        )
    ):
        roles.append("strong_comparison")
    if any(token in text for token in ("risk", "failure", "negative", "风险", "失败")):
        roles.append("risk")
    if any(
        token in text
        for token in (
            "parallel",
            "alternative",
            "module",
            "mechanism",
            "并行",
            "替代",
            "模块",
            "机制",
        )
    ):
        roles.append("parallel_method")
    if any(
        token in text for token in ("gap", "limitation", "problem", "缺口", "局限", "不足")
    ):
        roles.append("gap")
    return tuple(dict.fromkeys(roles))


def _role_from_text(value: str) -> EvidenceRole:
    roles = _roles_from_text(value)
    return roles[0] if roles else "other"
'''
        if old not in text:
            raise RuntimeError("role block not found")
        text = text.replace(old, new, 1)

    retrieval_start = text.index("def _retrieval_roles(")
    retrieval_end = text.index("\n\ndef _evidence_reviews", retrieval_start)
    retrieval_block = text[retrieval_start:retrieval_end]
    if "queries_by_gap" not in retrieval_block:
        new = '''def _retrieval_roles(
    state: PaperAgentState, gap_roles: dict[str, EvidenceRole]
) -> tuple[EvidenceRole, ...]:
    roles: list[EvidenceRole] = [role for role in gap_roles.values() if role != "other"]
    method = state.get("method")
    plan = state.get("plan")
    if plan is not None:
        queries_by_gap: dict[str, list[str]] = {}
        for query in plan.search_queries:
            queries_by_gap.setdefault(query.gap_id, []).append(query.query)
        for gap in plan.evidence_gaps:
            text = " ".join((gap.description, *queries_by_gap.get(gap.gap_id, [])))
            roles.extend(_roles_from_text(text))
    if method is not None:
        roles.append("baseline")
        if method.methodology_plan.modules:
            roles.append("parallel_method")
        if any(
            experiment.arm_type is ExperimentArmType.STRONG_COMPARISON
            for experiment in method.methodology_plan.experiments
        ):
            roles.append("strong_comparison")
    if plan is not None and plan.evidence_gaps:
        roles.append("gap")
    if plan is not None and plan.risks:
        roles.append("risk")
    return tuple(dict.fromkeys(roles))
'''
        text = text[:retrieval_start] + new + text[retrieval_end:]

    if "def _supplied_material_reviews" not in text:
        marker = "def _evidence_reviews(\n"
        helper = '''_SUPPLIED_REF = re.compile(
    r"^(?P<title>.+?) \\[declared role: (?P<role>.+?)\\]$",
    re.IGNORECASE,
)


def _supplied_material_reviews(
    state: PaperAgentState,
    *,
    existing_count: int,
) -> tuple[EvidenceReview, ...]:
    request = state.get("request")
    if request is None or existing_count >= len(request.user_material_refs):
        return ()
    reviews: list[EvidenceReview] = []
    for reference in request.user_material_refs[existing_count:]:
        match = _SUPPLIED_REF.match(reference.strip())
        declared_role = match.group("role").strip() if match else "other"
        digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
        role = _role_from_text(declared_role)
        reviews.append(
            EvidenceReview(
                evidence_id=f"user-material:{digest}",
                source_type="user_material",
                identity_verified=False,
                relevance_reviewed=False,
                relevance_passed=False,
                accepted=False,
                role=role,
                core_evidence=role in {"baseline", "gap", "parallel_method"},
                source_is_supplied_material=True,
                role_compatible=None,
            )
        )
    return tuple(reviews)


'''
        if marker not in text:
            raise RuntimeError("evidence review marker not found")
        text = text.replace(marker, helper + marker, 1)

    evidence_start = text.index("def _evidence_reviews(")
    evidence_end = text.index("\n\ndef _baseline_trace", evidence_start)
    evidence_block = text[evidence_start:evidence_end]
    if "_supplied_material_reviews" not in evidence_block:
        old = "    return tuple(reviews)\n"
        new = '''    supplied_count = sum(item.source_is_supplied_material for item in reviews)
    reviews.extend(_supplied_material_reviews(state, existing_count=supplied_count))
    return tuple(reviews)
'''
        if old not in evidence_block:
            raise RuntimeError("evidence review return not found")
        evidence_block = evidence_block.replace(old, new, 1)
        text = text[:evidence_start] + evidence_block + text[evidence_end:]

    ADAPTER.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    if "test_blocked_pre_retrieval_state_records_plan_inference_and_supplied_role" in text:
        return
    text += r'''


def test_blocked_pre_retrieval_state_records_plan_inference_and_supplied_role() -> None:
    plan = ResearchPlan(
        status="ready",
        problem_statement="Apply MobileNetV3 to lightweight plant-disease recognition.",
        scope="Public dataset, baseline, and efficiency evidence before deployment choices.",
        evidence_gaps=[
            EvidenceGap(
                gap_id="baseline_comparison",
                description="MobileNetV3 baseline and strong comparison evidence",
            ),
            EvidenceGap(
                gap_id="mechanism_limitation",
                description="mechanism limitation and parallel alternatives",
            ),
        ],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="baseline_comparison",
                query="MobileNetV3 plant disease baseline strong comparison",
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q2",
                gap_id="mechanism_limitation",
                query="plant disease limitation parallel mechanism risk",
                source_types=["paper"],
            ),
        ],
        success_criteria=["Find a reproducible baseline."],
        risks=["dataset and deployment device remain unknown"],
        clarification_question="Which dataset and device should constrain the pilot?",
    )
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="我上传了 MobileNetV3 论文，想用于轻量化植物病害识别",
                user_material_refs=[
                    "Searching for MobileNetV3 [declared role: baseline_or_backbone_candidate]"
                ],
            ),
            "plan": plan,
        },
    )

    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="at-017-mobilenetv3-plant-disease-supplied"),
    )

    assert trace.fact_partitions.inferred == (plan.problem_statement, plan.scope)
    assert set(trace.retrieval_roles) == {
        "baseline",
        "gap",
        "parallel_method",
        "strong_comparison",
        "risk",
    }
    supplied = [item for item in trace.evidence_reviews if item.source_is_supplied_material]
    assert len(supplied) == 1
    assert supplied[0].source_type == "user_material"
    assert supplied[0].role == "baseline"
    assert supplied[0].accepted is False
    assert supplied[0].identity_verified is False


def test_empty_state_uses_user_objective_without_claiming_external_verification() -> None:
    state = cast(
        PaperAgentState,
        {"request": ResearchRequest(question="面向电商场景的多行为推荐系统")},
    )

    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="at-015-multibehavior-recommendation"),
    )

    assert trace.fact_partitions.verified == (
        "User-declared research objective: 面向电商场景的多行为推荐系统",
    )
    assert trace.fact_partitions.inferred == ()
    assert trace.fact_partitions.proposed == ()
'''
    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_adapter()
    patch_tests()


if __name__ == "__main__":
    main()
