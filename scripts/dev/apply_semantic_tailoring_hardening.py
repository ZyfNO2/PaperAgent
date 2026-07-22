from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def block(value: str) -> str:
    return dedent(value).lstrip("\n")


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched {path}")


def patch_method_selection() -> None:
    path = "src/paperagent/method_design_draft.py"
    replace_once(
        path,
        block(
            '''
            def _declared_baseline_titles(references: list[str]) -> tuple[str, ...]:
                titles: list[str] = []
                for reference in references:
                    match = _DECLARED_ROLE_SUFFIX.search(reference)
                    if match is None or "baseline" not in match.group("role").casefold():
                        continue
                    title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
                    if title and title not in titles:
                        titles.append(title)
                return tuple(titles)
            '''
        ),
        block(
            '''
            def _declared_baseline_titles(references: list[str]) -> tuple[str, ...]:
                titles: list[str] = []
                for reference in references:
                    match = _DECLARED_ROLE_SUFFIX.search(reference)
                    if match is None or "baseline" not in match.group("role").casefold():
                        continue
                    title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
                    if title and title not in titles:
                        titles.append(title)
                return tuple(titles)


            def _declared_module_titles(references: list[str]) -> tuple[str, ...]:
                titles: list[str] = []
                for reference in references:
                    match = _DECLARED_ROLE_SUFFIX.search(reference)
                    if match is None:
                        continue
                    role = match.group("role").casefold()
                    if "baseline" in role or not any(token in role for token in ("module", "parallel")):
                        continue
                    title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
                    if title and title not in titles:
                        titles.append(title)
                return tuple(titles)
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                if not papers:
                    return None
                return max(papers, key=_baseline_evidence_rank)


            def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
            '''
        ),
        block(
            '''
                if not papers:
                    return None
                return max(papers, key=_baseline_evidence_rank)


            def _resolve_baseline_evidence(
                references: list[str],
                candidates: tuple[EvidenceItem, ...],
            ) -> EvidenceItem | None:
                """Honor a declared baseline as a hard identity constraint.

                A missed declared identity must remain unresolved. It must never silently fall
                through to an inferred or repository-backed alternative. Alternatives are only
                eligible when the user did not declare a baseline.
                """

                if _declared_baseline_titles(references):
                    return _select_declared_baseline_evidence(references, candidates)
                return _select_inferred_baseline_evidence(
                    candidates
                ) or _select_repository_backed_direct_baseline(candidates)


            def _comparator_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                selected = _select_declared_baseline_evidence(
                    references, candidates
                ) or _select_inferred_baseline_evidence(candidates)
            '''
        ),
        block(
            '''
                selected = _resolve_baseline_evidence(references, candidates)
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
            def _select_module_evidence(
                candidates: tuple[EvidenceItem, ...],
                *,
                baseline: EvidenceItem | None,
            ) -> EvidenceItem | None:
                papers = tuple(
                    item
                    for item in candidates
                    if item.source_type == "paper"
                    and item.metadata.get("comparator_candidate") != "inferred"
                    and item.metadata.get("relation") != "comparator_role_query"
                )
                if not papers:
                    return None
                baseline_id = baseline.evidence_id if baseline is not None else None
                return max(
                    papers,
                    key=lambda item: _module_evidence_rank(
                        item,
                        baseline_evidence_id=baseline_id,
                    ),
                )
            '''
        ),
        block(
            '''
            def _select_module_evidence(
                references: list[str],
                candidates: tuple[EvidenceItem, ...],
                *,
                baseline: EvidenceItem | None,
            ) -> EvidenceItem | None:
                declared_module_titles = _declared_module_titles(references)
                for declared_title in declared_module_titles:
                    for item in candidates:
                        if (
                            item.source_type == "paper"
                            and _titles_equivalent(item.title, declared_title)
                            and (baseline is None or item.evidence_id != baseline.evidence_id)
                        ):
                            return item

                baseline_id = baseline.evidence_id if baseline is not None else None
                papers = tuple(
                    item
                    for item in candidates
                    if item.source_type == "paper"
                    and item.evidence_id != baseline_id
                    and item.metadata.get("baseline_candidate") not in {"declared", "inferred"}
                    and item.metadata.get("comparator_candidate") != "inferred"
                    and item.metadata.get("relation")
                    not in {"baseline_role_query", "comparator_role_query", "declared_identity"}
                    and not _is_review_evidence(item.title, item.summary)
                )
                if papers:
                    return max(
                        papers,
                        key=lambda item: _module_evidence_rank(
                            item,
                            baseline_evidence_id=baseline_id,
                        ),
                    )

                # Backward-compatible title-only discovery may use one paper to motivate a
                # baseline and a candidate mechanism, but the scorer will not award independent
                # module provenance unless the trace binds a parallel_method review role.
                if not _declared_baseline_titles(references):
                    return baseline
                return None
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
                baseline_evidence = _select_declared_baseline_evidence(
                    list(request.user_material_refs), method_evidence
                ) or _select_inferred_baseline_evidence(method_evidence)
                if baseline_evidence is None:
                    baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)
                module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)
            '''
        ),
        block(
            '''
                request_references = list(request.user_material_refs)
                declared_baseline_titles = _declared_baseline_titles(request_references)
                baseline_evidence = _resolve_baseline_evidence(request_references, method_evidence)
                module_primary = _select_module_evidence(
                    request_references,
                    method_evidence,
                    baseline=baseline_evidence,
                )
            '''
        ),
    )


def patch_scorer() -> None:
    path = "scripts/score_academic_tailoring_retrieval_v1.py"
    replace_once(
        path,
        block(
            '''
            _INFERRED_BASELINE_RELATIONS = frozenset(
                {
                    "baseline_role_query",
                    "parallel_via_dataset",
                    "direct_query",
                }
            )
            '''
        ),
        block(
            '''
            _INFERRED_BASELINE_RELATIONS = frozenset(
                {
                    "baseline_role_query",
                    "parallel_via_dataset",
                }
            )
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
            def _accepted_asset_matches(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
                return sum(any(_asset_matches_item(asset, item) for item in items) for asset in assets)


            def _dataset_asset_score(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
            '''
        ),
        block(
            '''
            def _accepted_asset_matches(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
                return sum(any(_asset_matches_item(asset, item) for item in items) for asset in assets)


            _MODULE_ROLE_CUES = (
                "module",
                "parallel",
                "adaptation",
                "imputation",
                "attention",
                "fusion",
                "augmentation",
                "mechanism",
                "few-shot",
            )


            def _paper_asset_role(asset: dict[str, Any]) -> str:
                role = str(asset.get("role", "")).casefold()
                if "baseline" in role:
                    return "baseline"
                if "comparison" in role or "comparator" in role:
                    return "strong_comparison"
                if any(cue in role for cue in _MODULE_ROLE_CUES):
                    return "module"
                return "other"


            def _role_bound_paper_asset_matches(
                assets: list[dict[str, Any]],
                *,
                accepted_papers: list[dict[str, Any]],
                baseline_source_item: dict[str, Any] | None,
                module_source_items: list[dict[str, Any]],
                comparison_source_items: list[dict[str, Any]],
            ) -> int:
                matched = 0
                for asset in assets:
                    role = _paper_asset_role(asset)
                    candidates = {
                        "baseline": [baseline_source_item] if baseline_source_item is not None else [],
                        "module": module_source_items,
                        "strong_comparison": comparison_source_items,
                        "other": accepted_papers,
                    }[role]
                    if any(_asset_matches_item(asset, item) for item in candidates):
                        matched += 1
                return matched


            def _module_contract_complete(item: Any) -> bool:
                return all(
                    isinstance(value, str) and bool(value.strip())
                    for value in (
                        item.input_semantics,
                        item.output_semantics,
                        item.input_shape,
                        item.output_shape,
                        item.optimization_interaction,
                        item.failure_mode,
                        item.implementation_switch,
                    )
                )


            def _dataset_asset_score(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                unresolved = (
                    "unresolved",
                    "not yet",
                    "unknown",
                    "select and freeze",
                    "preserve the documented",
                    "待确定",
                    "未确定",
                    "未知",
                )
            '''
        ),
        block(
            '''
                unresolved = (
                    "unresolved",
                    "not yet",
                    "unknown",
                    "select and freeze",
                    "preserve the documented",
                    "freeze the official or documented",
                    "match input construction",
                    "match epochs or steps",
                    "task-specific representation",
                    "selected insertion point",
                    "待确定",
                    "未确定",
                    "未知",
                )
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                accepted_papers = [item for item in accepted_items if item.get("source_type") == "paper"]
                accepted_repos = [item for item in accepted_items if item.get("source_type") == "repository"]
                accepted_datasets = [item for item in accepted_items if item.get("source_type") == "dataset"]
                matched_papers = _accepted_asset_matches(paper_assets, accepted_papers)
                matched_repos = _accepted_asset_matches(repo_assets, accepted_repos)
                matched_datasets = _accepted_asset_matches(dataset_assets, accepted_datasets)

                baseline = trace.baseline
            '''
        ),
        block(
            '''
                accepted_papers = [item for item in accepted_items if item.get("source_type") == "paper"]
                accepted_repos = [item for item in accepted_items if item.get("source_type") == "repository"]
                accepted_datasets = [item for item in accepted_items if item.get("source_type") == "dataset"]
                matched_repos = _accepted_asset_matches(repo_assets, accepted_repos)
                matched_datasets = _accepted_asset_matches(dataset_assets, accepted_datasets)
                accepted_review_by_id = {
                    item.evidence_id: item
                    for item in trace.evidence_reviews
                    if item.accepted and item.identity_verified and item.relevance_passed
                }

                baseline = trace.baseline
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                baseline_identity_acceptable = baseline_identity_status in {
                    "exact_target",
                    "evidence_bound_alternative",
                }

                identity_score = 0
                if accepted_papers:
                    identity_score += 5
                if paper_assets:
                    identity_score += round(10 * matched_papers / len(paper_assets))
                else:
                    identity_score += 10
                if baseline_identity_status == "evidence_bound_alternative":
                    identity_score += 5
                identity_score = min(15, identity_score)

                baseline_score = 0
                if baseline is not None and baseline_source_item is not None:
                    baseline_score += 5
                    if baseline_target_match:
                        baseline_score += 5
                    elif baseline_identity_status == "evidence_bound_alternative":
                        baseline_score += 3
                    if baseline.source_evidence_id:
                        baseline_score += 2
                    if baseline.version_or_commit:
                        baseline_score += 3
                baseline_score = min(15, baseline_score)
            '''
        ),
        block(
            '''
                baseline_identity_acceptable = baseline_identity_status in {
                    "exact_target",
                    "evidence_bound_alternative",
                }
                baseline_source_id = baseline.source_evidence_id if baseline is not None else None
                module_source_ids = {
                    item.evidence_id
                    for item in trace.modules
                    if item.evidence_id
                    and item.evidence_id != baseline_source_id
                    and item.evidence_id in accepted_items_by_id
                    and accepted_review_by_id.get(item.evidence_id) is not None
                    and accepted_review_by_id[item.evidence_id].role == "parallel_method"
                }
                comparison_source_ids = {
                    evidence_id
                    for evidence_id, review in accepted_review_by_id.items()
                    if review.role == "strong_comparison"
                }
                module_source_items = [accepted_items_by_id[item] for item in module_source_ids]
                comparison_source_items = [
                    accepted_items_by_id[item]
                    for item in comparison_source_ids
                    if item in accepted_items_by_id
                ]
                matched_papers = _role_bound_paper_asset_matches(
                    paper_assets,
                    accepted_papers=accepted_papers,
                    baseline_source_item=baseline_source_item,
                    module_source_items=module_source_items,
                    comparison_source_items=comparison_source_items,
                )

                identity_score = 0
                if accepted_papers:
                    identity_score += 5
                if paper_assets:
                    identity_score += round(10 * matched_papers / len(paper_assets))
                else:
                    identity_score += 10
                identity_score = min(15, identity_score)

                baseline_score = 0
                if baseline is not None and baseline_source_item is not None and baseline_identity_acceptable:
                    baseline_score += 10 if baseline_target_match else 7
                    if baseline.source_evidence_id:
                        baseline_score += 2
                    if baseline.version_or_commit:
                        baseline_score += 3
                baseline_score = min(15, baseline_score)
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                accepted_review_by_id = {
                    item.evidence_id: item for item in trace.evidence_reviews if item.accepted
                }
                gap_evidence_count = sum(
            '''
        ),
        block(
            '''
                gap_evidence_count = sum(
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                valid_evidence_ids = set(accepted_items_by_id)
                module_score = 0
                evidence_backed_modules = 0
                if trace.modules:
                    module_score += 3
                    evidence_backed_modules = sum(
                        item.evidence_id in valid_evidence_ids for item in trace.modules
                    )
                    role_count = sum(bool(item.original_role and item.proposed_role) for item in trace.modules)
                    module_score += round(4 * evidence_backed_modules / len(trace.modules))
                    module_score += round(3 * role_count / len(trace.modules))
                elif trace.module_design_deferred and trace.module_defer_reason:
                    module_score = 4
                module_score = min(10, module_score)

                compatibility_score = 0
                if trace.modules:
                    semantic_count = sum(
                        bool(item.input_semantics and item.output_semantics and item.failure_mode)
                        for item in trace.modules
                    )
                    switch_count = sum(bool(item.implementation_switch) for item in trace.modules)
                    explicitly_compatible_count = sum(item.role_compatible is True for item in trace.modules)
                    compatibility_score += round(6 * semantic_count / len(trace.modules))
                    compatibility_score += round(2 * switch_count / len(trace.modules))
                    compatibility_score += round(4 * explicitly_compatible_count / len(trace.modules))
                    compatibility_score += round(3 * evidence_backed_modules / len(trace.modules))
                elif trace.module_design_deferred:
                    compatibility_score = 3
                compatibility_score = min(15, compatibility_score)

                hypothesis_score = 0
                if _complete_hypothesis(trace):
                    hypothesis_score += 3
                    if baseline_identity_acceptable and accepted_items:
                        hypothesis_score += 2
            '''
        ),
        block(
            '''
                valid_evidence_ids = set(accepted_items_by_id)
                module_score = 0
                evidence_backed_modules = 0
                role_bound_modules = [
                    item
                    for item in trace.modules
                    if item.evidence_id in module_source_ids
                ]
                if trace.modules:
                    evidence_backed_modules = len(role_bound_modules)
                    role_count = sum(
                        bool(item.original_role and item.proposed_role) for item in role_bound_modules
                    )
                    module_score += round(7 * evidence_backed_modules / len(trace.modules))
                    module_score += round(3 * role_count / len(trace.modules))
                elif trace.module_design_deferred and trace.module_defer_reason:
                    module_score = 4
                module_score = min(10, module_score)

                compatibility_score = 0
                verified_contract_modules = [
                    item
                    for item in role_bound_modules
                    if _module_contract_complete(item)
                    and accepted_review_by_id[item.evidence_id].role_compatible is True
                    and item.role_compatible is not False
                ]
                if trace.modules:
                    compatibility_score = round(15 * len(verified_contract_modules) / len(trace.modules))
                elif trace.module_design_deferred:
                    compatibility_score = 3
                compatibility_score = min(15, compatibility_score)

                hypothesis_score = 0
                if (
                    _complete_hypothesis(trace)
                    and baseline_identity_acceptable
                    and role_bound_modules
                ):
                    hypothesis_score = 5
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                if arm_types & {"full", "single_module", "interaction"}:
                    experiment_score += 2
            '''
        ),
        block(
            '''
                if arm_types & {"full", "single_module", "interaction"} and role_bound_modules:
                    experiment_score += 2
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                if any(item.role_compatible is False for item in trace.modules):
                    hard_failures.append("unsupported_compatibility")
                if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
                    hard_failures.append("module_not_bound_to_accepted_evidence")
            '''
        ),
        block(
            '''
                if any(item.role_compatible is False for item in trace.modules):
                    hard_failures.append("unsupported_compatibility")
                if any(item.evidence_id not in valid_evidence_ids for item in trace.modules):
                    hard_failures.append("module_not_bound_to_accepted_evidence")
                if baseline_source_id and any(
                    item.evidence_id == baseline_source_id for item in trace.modules
                ):
                    hard_failures.append("baseline_reused_as_module_evidence")
                if any(
                    item.evidence_id in valid_evidence_ids
                    and (
                        accepted_review_by_id.get(item.evidence_id) is None
                        or accepted_review_by_id[item.evidence_id].role != "parallel_method"
                    )
                    for item in trace.modules
                ):
                    hard_failures.append("module_evidence_role_mismatch")
                if trace.modules and len(verified_contract_modules) != len(trace.modules):
                    hard_failures.append("module_compatibility_not_independently_verified")
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                if trace.decision == "ACCEPT" and (
                    hard_failures
                    or not baseline_identity_acceptable
                    or dataset_score < 5
                    or repository_score < 3
                ):
                    hard_failures.append("unsupported_acceptance")
            '''
        ),
        block(
            '''
                if trace.decision == "GO" and (
                    hard_failures
                    or not baseline_identity_acceptable
                    or not role_bound_modules
                    or len(verified_contract_modules) != len(trace.modules)
                    or dataset_score < 5
                    or repository_score < 3
                    or experiment_score < 7
                ):
                    hard_failures.append("unsupported_go_decision")
            '''
        ),
    )
    replace_once(
        path,
        block(
            '''
                        "evidence_backed_module_count": evidence_backed_modules,
                    },
            '''
        ),
        block(
            '''
                        "evidence_backed_module_count": evidence_backed_modules,
                        "role_bound_module_evidence_ids": sorted(module_source_ids),
                        "verified_module_contract_count": len(verified_contract_modules),
                        "role_bound_paper_asset_matches": matched_papers,
                    },
            '''
        ),
    )


def write_tests() -> None:
    Path("tests/methodology/test_role_bound_method_selection.py").write_text(
        block(
            '''
            from __future__ import annotations

            from datetime import UTC, datetime

            from paperagent.method_design_draft import (
                _resolve_baseline_evidence,
                _select_module_evidence,
            )
            from paperagent.schemas.evidence import EvidenceItem


            def _paper(
                evidence_id: str,
                title: str,
                *,
                relation: str,
                baseline_candidate: str | None = None,
            ) -> EvidenceItem:
                metadata = {"relation": relation, "rank_score": "0.9"}
                if baseline_candidate is not None:
                    metadata["baseline_candidate"] = baseline_candidate
                return EvidenceItem(
                    evidence_id=evidence_id,
                    source_type="paper",
                    title=title,
                    locator=f"doi:10.1000/{evidence_id}",
                    retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
                    verification_status="accepted",
                    supports_gap_ids=["baseline_comparison"],
                    summary=f"Verified evidence for {title}.",
                    content_hash=f"sha256:{evidence_id}",
                    metadata=metadata,
                )


            def test_declared_baseline_miss_never_falls_through_to_inferred_paper() -> None:
                time_machine = _paper(
                    "ev-time-machine",
                    "TimeMachine: A Time Series is Worth 4 Mambas for Long-Term Forecasting",
                    relation="baseline_role_query",
                    baseline_candidate="inferred",
                )
                selected = _resolve_baseline_evidence(
                    [
                        "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers "
                        "[declared role:baseline]"
                    ],
                    (time_machine,),
                )
                assert selected is None


            def test_declared_parallel_module_is_bound_independently_from_baseline() -> None:
                bert = _paper(
                    "ev-bert",
                    "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    relation="declared_identity",
                    baseline_candidate="declared",
                )
                lora = _paper(
                    "ev-lora",
                    "LoRA: Low-Rank Adaptation of Large Language Models",
                    relation="declared_identity",
                )
                references = [
                    f"{bert.title} [declared role:baseline]",
                    f"{lora.title} [declared role:parallel_module_source]",
                ]
                baseline = _resolve_baseline_evidence(references, (bert, lora))
                module = _select_module_evidence(references, (bert, lora), baseline=baseline)
                assert baseline is bert
                assert module is lora
                assert module.evidence_id != baseline.evidence_id
            '''
        ),
        encoding="utf-8",
    )
    Path("tests/evaluation/test_semantic_role_bound_retrieval_scorer.py").write_text(
        block(
            '''
            from __future__ import annotations

            import importlib.util
            from pathlib import Path

            from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace


            SCRIPT = Path(__file__).parents[2] / "scripts" / "score_academic_tailoring_retrieval_v1.py"
            SPEC = importlib.util.spec_from_file_location("retrieval_scorer", SCRIPT)
            assert SPEC is not None and SPEC.loader is not None
            scorer = importlib.util.module_from_spec(SPEC)
            SPEC.loader.exec_module(scorer)


            def _case() -> dict[str, object]:
                return {
                    "case_id": "atr-v1-003-nlp-bert-lora-clinc",
                    "case_type": "baseline_plus_parallel_paper",
                    "domain": "nlp",
                    "public_input": {
                        "supplied_materials": [
                            {
                                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                                "declared_role": "baseline",
                            },
                            {
                                "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                                "declared_role": "parallel_module_source",
                            },
                        ]
                    },
                    "gold": {
                        "expected_assets": [
                            {
                                "kind": "paper",
                                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                                "role": "baseline",
                            },
                            {
                                "kind": "paper",
                                "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                                "role": "module source",
                            },
                        ],
                        "baseline_decision": {
                            "canonical": "BERT-base classifier with a linear intent head"
                        },
                    },
                }


            def _state() -> dict[str, object]:
                items = [
                    {
                        "evidence_id": "ev-bert",
                        "source_type": "paper",
                        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                        "locator": "arxiv:1810.04805",
                        "metadata": {"relation": "declared_identity"},
                    },
                    {
                        "evidence_id": "ev-lora",
                        "source_type": "paper",
                        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                        "locator": "arxiv:2106.09685",
                        "metadata": {"relation": "declared_identity"},
                    },
                ]
                return {
                    "evidence": {
                        "items": items,
                        "accepted_ids": ["ev-bert", "ev-lora"],
                    }
                }


            def _trace(*, baseline_id: str, module_id: str, module_role: str) -> AcademicTailoringRunTrace:
                return AcademicTailoringRunTrace.model_validate(
                    {
                        "case_id": "atr-v1-003-nlp-bert-lora-clinc",
                        "fact_partitions": {
                            "verified": ["paper identities verified"],
                            "inferred": ["compatibility remains conditional"],
                            "proposed": ["LoRA pilot"],
                            "unknown": [],
                        },
                        "retrieval_roles": ["baseline", "parallel_method"],
                        "evidence_reviews": [
                            {
                                "evidence_id": "ev-bert",
                                "source_type": "paper",
                                "identity_verified": True,
                                "relevance_reviewed": True,
                                "relevance_passed": True,
                                "accepted": True,
                                "role": "baseline",
                                "core_evidence": True,
                                "role_compatible": True,
                            },
                            {
                                "evidence_id": "ev-lora",
                                "source_type": "paper",
                                "identity_verified": True,
                                "relevance_reviewed": True,
                                "relevance_passed": True,
                                "accepted": True,
                                "role": module_role,
                                "core_evidence": True,
                                "role_compatible": True,
                            },
                        ],
                        "clarification_questions": [],
                        "resolved_unknowns": [],
                        "baseline": {
                            "name": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                            "source_evidence_id": baseline_id,
                            "version_or_commit": "checkpoint and commit frozen",
                            "dataset": "CLINC150 / OOS-Eval",
                            "split": "fixed 10-shot sampler seeds with a separate OOS test split",
                            "metrics": ["macro-F1", "OOS recall"],
                            "environment": "locked Python environment",
                            "seed_policy": "1, 2, 3",
                        },
                        "hypothesis": {
                            "condition": "ten examples per intent",
                            "limitation": "full fine-tuning overfits",
                            "mechanism": "low-rank updates constrain adaptation",
                            "intervention": "LoRA on query and value projections",
                            "target_metric": "macro-F1",
                            "guardrail": "OOS recall must not degrade",
                        },
                        "modules": [
                            {
                                "module_id": "lora_qv",
                                "evidence_id": module_id,
                                "original_role": "parameter-efficient transformer adaptation",
                                "proposed_role": "BERT query/value low-rank updates",
                                "input_semantics": "BERT self-attention hidden states",
                                "output_semantics": "adapted query and value projections",
                                "input_shape": "batch x tokens x hidden",
                                "output_shape": "batch x tokens x hidden",
                                "optimization_interaction": "freeze base weights and optimize A/B matrices",
                                "compute_cost": "rank-8 adapters",
                                "failure_mode": "rank bottleneck underfits rare intents",
                                "implementation_switch": "enable_lora_qv",
                                "role_compatible": True,
                            }
                        ],
                        "stitch_order": ["bert", "lora_qv", "intent_head"],
                        "experiments": [
                            {
                                "experiment_id": "e0",
                                "arm_type": "baseline",
                                "dataset": "CLINC150 / OOS-Eval",
                                "split": "fixed 10-shot sampler seeds; independent OOS test set",
                                "preprocessing": "BERT-base uncased tokenizer, max length 64",
                                "tuning_budget": "20 epochs, identical optimizer grid and early stopping",
                                "metrics": ["macro-F1", "OOS recall"],
                                "seeds": [1, 2, 3],
                                "uncertainty_reporting": "mean and standard deviation",
                                "stopping_criteria": "stop if OOS recall drops by more than 2 points",
                            },
                            {
                                "experiment_id": "e1",
                                "arm_type": "single_module",
                                "included_modules": ["lora_qv"],
                                "dataset": "CLINC150 / OOS-Eval",
                                "split": "fixed 10-shot sampler seeds; independent OOS test set",
                                "preprocessing": "BERT-base uncased tokenizer, max length 64",
                                "tuning_budget": "20 epochs, identical optimizer grid and early stopping",
                                "metrics": ["macro-F1", "OOS recall"],
                                "seeds": [1, 2, 3],
                                "uncertainty_reporting": "mean and standard deviation",
                                "stopping_criteria": "stop if gain disappears under matched budget",
                            },
                        ],
                        "decision": "REVISE",
                        "pilot_recommended": True,
                        "next_actions": ["freeze implementation"],
                        "stop_conditions": ["baseline reproduction fails", "OOS recall degrades"],
                        "stronger_baselines_considered": True,
                        "negative_results_visible": True,
                    }
                )


            def test_module_cannot_reuse_baseline_evidence_or_baseline_role() -> None:
                result = scorer._score_case(
                    _case(),
                    _state(),
                    _trace(baseline_id="ev-bert", module_id="ev-bert", module_role="baseline"),
                    prompt_leakage=False,
                    minimum_score=80,
                )
                assert "baseline_reused_as_module_evidence" in result["hard_failures"]
                assert "module_evidence_role_mismatch" in result["hard_failures"]
                assert result["dimensions"]["module_provenance_and_role"] == 0


            def test_role_bound_bert_and_lora_receive_role_specific_credit() -> None:
                result = scorer._score_case(
                    _case(),
                    _state(),
                    _trace(baseline_id="ev-bert", module_id="ev-lora", module_role="parallel_method"),
                    prompt_leakage=False,
                    minimum_score=80,
                )
                assert "wrong_paper_identity" not in result["hard_failures"]
                assert "module_evidence_role_mismatch" not in result["hard_failures"]
                assert "module_compatibility_not_independently_verified" not in result["hard_failures"]
                assert result["matched_assets"]["papers"] == [2, 2]
                assert result["dimensions"]["module_provenance_and_role"] == 10
                assert result["dimensions"]["semantic_and_interface_compatibility"] == 15
            '''
        ),
        encoding="utf-8",
    )


def main() -> None:
    patch_method_selection()
    patch_scorer()
    write_tests()


if __name__ == "__main__":
    main()
