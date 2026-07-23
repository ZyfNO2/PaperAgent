from __future__ import annotations

from pathlib import Path
from textwrap import dedent, indent


def code(value: str, spaces: int = 0) -> str:
    normalized = dedent(value).lstrip("\n")
    return indent(normalized, " " * spaces) if spaces else normalized


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 1:
        file.write_text(text.replace(old, new), encoding="utf-8")
        print(f"patched {path}")
        return
    if new in text:
        print(f"already patched {path}")
        return
    raise RuntimeError(f"{path}: expected one match, found {count}")


def patch_dataset_relation_priority() -> None:
    old = code(
        """
        def _dataset_relation_names(
            query: str,
            papers: Iterable[PaperRecord],
        ) -> tuple[str, ...]:
            paper_list = tuple(papers)
            blocked = {
                token.casefold()
                for paper in paper_list
                for token in _distinctive_dataset_tokens(paper.canonical_title)
            }
            names = [name for name in _dataset_names_from_query(query) if name.casefold() not in blocked]
            for paper in paper_list:
                for name in _explicit_dataset_names_from_text(
                    f"{paper.canonical_title}\\n{paper.abstract or ''}"
                ):
                    if name not in names:
                        names.append(name)
            return tuple(names)
        """
    )
    new = code(
        """
        def _dataset_relation_names(
            query: str,
            papers: Iterable[PaperRecord],
        ) -> tuple[str, ...]:
            paper_list = tuple(papers)
            blocked = {
                token.casefold()
                for paper in paper_list
                for token in _distinctive_dataset_tokens(paper.canonical_title)
            }
            # An explicitly named dataset is a user-visible retrieval constraint. The
            # title-derived blocklist only suppresses uncued acronym/model guesses.
            names = list(_explicit_dataset_names_from_text(query))
            for name in _distinctive_dataset_tokens(query):
                if name.casefold() not in blocked and name not in names:
                    names.append(name)
            for paper in paper_list:
                for name in _explicit_dataset_names_from_text(
                    f"{paper.canonical_title}\\n{paper.abstract or ''}"
                ):
                    if name not in names:
                        names.append(name)
            return tuple(names)
        """
    )
    replace_once("src/paperagent/literature/adapter.py", old, new)


def patch_repository_backed_baseline() -> None:
    old = code(
        """
        def _select_inferred_baseline_evidence(
            candidates: tuple[EvidenceItem, ...],
        ) -> EvidenceItem | None:
            papers = tuple(
                item
                for item in candidates
                if item.source_type == "paper"
                and item.metadata.get("baseline_candidate") == "inferred"
                and item.metadata.get("relation") in {"baseline_role_query", "parallel_via_dataset"}
            )
            if not papers:
                return None
            return max(papers, key=_baseline_evidence_rank)
        """
    )
    new = (
        old
        + "\n\n"
        + code(
            '''
        def _select_repository_backed_direct_baseline(
            candidates: tuple[EvidenceItem, ...],
        ) -> EvidenceItem | None:
            """Select a verified task paper with an accepted author-linked repository.

            This is a last-resort baseline only when the user did not declare one and
            focused baseline retrieval produced no accepted candidate.
            """

            repository_parent_ids: set[str] = {
                parent_id
                for item in candidates
                if item.source_type == "repository"
                and item.metadata.get("relation") == "author_linked_from_verified_paper"
                for parent_id in (item.metadata.get("parent_paper_id"),)
                if parent_id
            }
            papers = tuple(
                item
                for item in candidates
                if item.source_type == "paper"
                and item.metadata.get("relation") == "direct_query"
                and item.evidence_id.removeprefix("ev-") in repository_parent_ids
                and not _is_review_evidence(item.title, item.summary)
            )
            if not papers:
                return None
            return max(papers, key=_baseline_evidence_rank)
        '''
        )
    )
    replace_once("src/paperagent/method_design_draft.py", old, new)

    replace_once(
        "src/paperagent/method_design_draft.py",
        "    ) or _select_inferred_baseline_evidence(method_evidence)\n"
        "    module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)\n",
        "    ) or _select_inferred_baseline_evidence(method_evidence)\n"
        "    if baseline_evidence is None and not declared_baseline_titles:\n"
        "        baseline_evidence = _select_repository_backed_direct_baseline(method_evidence)\n"
        "    module_primary = _select_module_evidence(method_evidence, baseline=baseline_evidence)\n",
    )


def patch_scorer_baseline_acceptance() -> None:
    helper = code(
        """
        def _has_author_linked_repository(
            baseline_source_item: dict[str, Any], accepted_items: list[dict[str, Any]]
        ) -> bool:
            evidence_id = str(baseline_source_item.get("evidence_id", ""))
            source_paper_id = evidence_id.removeprefix("ev-")
            if not source_paper_id:
                return False
            return any(
                item.get("source_type") == "repository"
                and isinstance(item.get("metadata"), dict)
                and item["metadata"].get("relation") == "author_linked_from_verified_paper"
                and item["metadata"].get("parent_paper_id") == source_paper_id
                for item in accepted_items
            )
        """
    )
    marker = "def _baseline_identity_status(\n"
    path = Path("scripts/score_academic_tailoring_retrieval_v1.py")
    text = path.read_text(encoding="utf-8")
    if "def _has_author_linked_repository(" not in text:
        if text.count(marker) != 1:
            raise RuntimeError("baseline identity marker missing")
        path.write_text(text.replace(marker, helper + "\n\n" + marker), encoding="utf-8")

    replace_once(
        str(path),
        "    baseline_targets: list[str],\n) -> str:\n",
        "    baseline_targets: list[str],\n    accepted_items: list[dict[str, Any]],\n) -> str:\n",
    )

    old_condition = code(
        """
        if (
            case.get("case_type") == "title_only"
            and baseline_source_item.get("source_type") == "paper"
            and baseline_candidate == "inferred"
            and relation in _INFERRED_BASELINE_RELATIONS
        ):
            return "evidence_bound_alternative"
        return "mismatch"
        """,
        4,
    )
    new_condition = code(
        """
        if case.get("case_type") == "title_only" and baseline_source_item.get(
            "source_type"
        ) == "paper":
            if baseline_candidate == "inferred" and relation in _INFERRED_BASELINE_RELATIONS:
                return "evidence_bound_alternative"
            if relation == "direct_query" and _has_author_linked_repository(
                baseline_source_item, accepted_items
            ):
                return "evidence_bound_alternative"
        return "mismatch"
        """,
        4,
    )
    replace_once(str(path), old_condition, new_condition)
    replace_once(
        str(path),
        "        baseline_targets=baseline_targets,\n    )\n",
        "        baseline_targets=baseline_targets,\n"
        "        accepted_items=accepted_items,\n"
        "    )\n",
    )


def patch_graph_recursion_budget() -> None:
    path = "src/paperagent/claw_benchmark_runtime.py"
    replace_once(
        path,
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        ") -> tuple[dict[str, Any], PaperAgentState]:\n",
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        "    recursion_limit: int = 100,\n"
        ") -> tuple[dict[str, Any], PaperAgentState]:\n",
    )
    replace_once(
        path,
        "    services = RuntimeServices(\n",
        "    if recursion_limit < 1:\n"
        '        raise ValueError("recursion_limit must be positive")\n'
        "\n"
        "    services = RuntimeServices(\n",
    )
    replace_once(
        path,
        '                "human_review_policy": "block",\n            }\n        },\n',
        '                "human_review_policy": "block",\n'
        "            },\n"
        '            "recursion_limit": recursion_limit,\n'
        "        },\n",
    )
    replace_once(
        path,
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        ") -> tuple[dict[str, Any], AcademicTailoringRunTrace]:\n",
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        "    recursion_limit: int = 100,\n"
        ") -> tuple[dict[str, Any], AcademicTailoringRunTrace]:\n",
    )
    replace_once(
        path,
        "        max_method_repairs=max_method_repairs,\n"
        "        max_evidence_items=max_evidence_items,\n"
        "    )\n",
        "        max_method_repairs=max_method_repairs,\n"
        "        max_evidence_items=max_evidence_items,\n"
        "        recursion_limit=recursion_limit,\n"
        "    )\n",
    )


def patch_runner_recursion_budget() -> None:
    path = "scripts/run_academic_tailoring_retrieval_v1.py"
    replace_once(
        path,
        "    graph_budgets: RunBudgets,\n    provider_call_budget_total: int,\n",
        "    graph_budgets: RunBudgets,\n"
        "    graph_recursion_limit: int,\n"
        "    provider_call_budget_total: int,\n",
    )
    replace_once(
        path,
        '            "graph": graph_budgets.model_dump(mode="json"),\n',
        '            "graph": {\n'
        '                **graph_budgets.model_dump(mode="json"),\n'
        '                "recursion_limit": graph_recursion_limit,\n'
        "            },\n",
    )
    replace_once(
        path,
        '    parser.add_argument("--max-evidence-items", type=int, default=120)\n'
        '    parser.add_argument("--provider-call-budget", type=int, default=480)\n',
        '    parser.add_argument("--max-evidence-items", type=int, default=120)\n'
        '    parser.add_argument("--recursion-limit", type=int, default=100)\n'
        '    parser.add_argument("--provider-call-budget", type=int, default=480)\n',
    )
    replace_once(
        path,
        "    if args.max_llm_calls < 1 or args.provider_call_budget < 1:\n"
        '        raise ValueError("LLM and provider budgets must be positive")\n',
        "    if (\n"
        "        args.max_llm_calls < 1\n"
        "        or args.provider_call_budget < 1\n"
        "        or args.recursion_limit < 1\n"
        "    ):\n"
        '        raise ValueError("LLM, provider, and recursion budgets must be positive")\n',
    )
    replace_once(
        path,
        "            graph_budgets=graph_budgets,\n"
        "            provider_call_budget_total=args.provider_call_budget,\n",
        "            graph_budgets=graph_budgets,\n"
        "            graph_recursion_limit=args.recursion_limit,\n"
        "            provider_call_budget_total=args.provider_call_budget,\n",
    )
    replace_once(
        path,
        "                max_method_repairs=graph_budgets.max_method_repairs,\n"
        "                max_evidence_items=graph_budgets.max_evidence_items,\n"
        '                task_id=f"atr-v1-{index:02d}",\n',
        "                max_method_repairs=graph_budgets.max_method_repairs,\n"
        "                max_evidence_items=graph_budgets.max_evidence_items,\n"
        "                recursion_limit=args.recursion_limit,\n"
        '                task_id=f"atr-v1-{index:02d}",\n',
    )


def patch_tests() -> None:
    budget_path = "tests/evals/test_academic_tailoring_diagnostic_budgets.py"
    replace_once(
        budget_path,
        "    assert args.max_evidence_items == 120\n    assert args.provider_call_budget == 480\n",
        "    assert args.max_evidence_items == 120\n"
        "    assert args.recursion_limit == 100\n"
        "    assert args.provider_call_budget == 480\n",
    )
    replace_once(
        budget_path,
        '            "--max-evidence-items",\n'
        '            "30",\n'
        '            "--provider-call-budget",\n',
        '            "--max-evidence-items",\n'
        '            "30",\n'
        '            "--recursion-limit",\n'
        '            "50",\n'
        '            "--provider-call-budget",\n',
    )
    replace_once(
        budget_path,
        "    assert args.max_evidence_items == 30\n    assert args.provider_call_budget == 120\n",
        "    assert args.max_evidence_items == 30\n"
        "    assert args.recursion_limit == 50\n"
        "    assert args.provider_call_budget == 120\n",
    )

    diagnostics_path = "tests/evals/test_academic_tailoring_retrieval_v1_diagnostics.py"
    replace_once(
        diagnostics_path,
        '        baseline_targets=["Hidden Reference Baseline"],\n    )\n',
        '        baseline_targets=["Hidden Reference Baseline"],\n'
        "        accepted_items=[source],\n"
        "    )\n",
    )
    replace_once(
        diagnostics_path,
        '        baseline_targets=["Declared Baseline"],\n    )\n',
        '        baseline_targets=["Declared Baseline"],\n'
        "        accepted_items=[source],\n"
        "    )\n",
    )
    diagnostics = Path(diagnostics_path)
    text = diagnostics.read_text(encoding="utf-8")
    marker = "def test_title_only_case_accepts_repo_backed_direct_baseline()"
    if marker not in text:
        text += "\n\n" + code(
            """
            def test_title_only_case_accepts_repo_backed_direct_baseline() -> None:
                case = {
                    "case_type": "title_only",
                    "public_input": {"supplied_materials": []},
                    "gold": {
                        "baseline_decision": {"canonical": "Reference Baseline"},
                        "expected_assets": [],
                    },
                }
                source = {
                    "evidence_id": "ev-paper-task",
                    "source_type": "paper",
                    "title": "Verified Task Paper",
                    "metadata": {"relation": "direct_query"},
                }
                repository = {
                    "evidence_id": "ev-repository-task",
                    "source_type": "repository",
                    "title": "authors/task-code",
                    "metadata": {
                        "relation": "author_linked_from_verified_paper",
                        "parent_paper_id": "paper-task",
                    },
                }

                status = _baseline_identity_status(
                    case,
                    baseline_name="Verified Task Paper",
                    baseline_source_item=source,
                    baseline_targets=["Reference Baseline"],
                    accepted_items=[source, repository],
                )

                assert status == "evidence_bound_alternative"
            """
        )
        diagnostics.write_text(text, encoding="utf-8")

    Path("tests/literature").mkdir(parents=True, exist_ok=True)
    Path("tests/literature/test_dataset_relation_priority.py").write_text(
        code(
            """
            from __future__ import annotations

            from types import SimpleNamespace
            from typing import cast

            from paperagent.literature.adapter import _dataset_relation_names
            from paperagent.schemas.literature import PaperRecord


            def test_explicit_query_dataset_survives_paper_title_blocklist() -> None:
                papers = (
                    cast(
                        PaperRecord,
                        SimpleNamespace(
                            canonical_title="DOTA-Aware Rotated Detector",
                            abstract="Compared with the UCAS-AOD dataset.",
                        ),
                    ),
                )
                names = _dataset_relation_names("DOTA dataset rotated object detection", papers)
                assert names[0] == "DOTA"
                assert "UCAS-AOD" in names


            def test_explicit_swat_dataset_is_not_replaced_by_neighbor_mentions() -> None:
                papers = (
                    cast(
                        PaperRecord,
                        SimpleNamespace(
                            canonical_title="SWaT Industrial Anomaly Benchmark",
                            abstract="Evaluation also references the WADI dataset.",
                        ),
                    ),
                )
                names = _dataset_relation_names("SWaT dataset anomaly detection", papers)
                assert names[0] == "SWaT"
                assert "WADI" in names
            """
        ),
        encoding="utf-8",
    )

    Path("tests/method").mkdir(parents=True, exist_ok=True)
    Path("tests/method/test_repo_backed_baseline.py").write_text(
        code(
            """
            from __future__ import annotations

            from types import SimpleNamespace
            from typing import cast

            from paperagent.method_design_draft import _select_repository_backed_direct_baseline
            from paperagent.schemas.evidence import EvidenceItem


            def _item(**values: object) -> EvidenceItem:
                return cast(EvidenceItem, SimpleNamespace(**values))


            def test_repo_backed_direct_paper_can_anchor_title_only_baseline() -> None:
                paper = _item(
                    evidence_id="ev-paper-deepgo",
                    source_type="paper",
                    title="DeepGO: predicting protein functions",
                    summary="Sequence-based protein function prediction.",
                    metadata={"relation": "direct_query", "rank_score": "0.87"},
                )
                higher_rank_without_repo = _item(
                    evidence_id="ev-paper-unbound",
                    source_type="paper",
                    title="Unbound Candidate",
                    summary="A task paper without linked implementation.",
                    metadata={"relation": "direct_query", "rank_score": "0.99"},
                )
                repository = _item(
                    evidence_id="ev-repository-deepgo",
                    source_type="repository",
                    title="bio-ontology-research-group/deepgo",
                    summary="Author-linked implementation.",
                    metadata={
                        "relation": "author_linked_from_verified_paper",
                        "parent_paper_id": "paper-deepgo",
                    },
                )
                selected = _select_repository_backed_direct_baseline(
                    (paper, higher_rank_without_repo, repository)
                )
                assert selected is paper


            def test_repo_backed_review_is_not_selected_as_baseline() -> None:
                review = _item(
                    evidence_id="ev-paper-review",
                    source_type="paper",
                    title="A survey of protein function prediction",
                    summary="Review and taxonomy.",
                    metadata={"relation": "direct_query", "rank_score": "1.0"},
                )
                repository = _item(
                    evidence_id="ev-repository-review",
                    source_type="repository",
                    title="example/review",
                    summary="Linked repository.",
                    metadata={
                        "relation": "author_linked_from_verified_paper",
                        "parent_paper_id": "paper-review",
                    },
                )
                assert _select_repository_backed_direct_baseline((review, repository)) is None
            """
        ),
        encoding="utf-8",
    )


def main() -> None:
    patch_dataset_relation_priority()
    patch_repository_backed_baseline()
    patch_scorer_baseline_acceptance()
    patch_graph_recursion_budget()
    patch_runner_recursion_budget()
    patch_tests()


if __name__ == "__main__":
    main()
