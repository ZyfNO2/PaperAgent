from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/paperagent/literature/adapter.py")
TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    source = path.read_text(encoding="utf-8")
    if marker not in source:
        source += addition
    path.write_text(source, encoding="utf-8")


def main() -> int:
    replace_once(
        ADAPTER,
        '''        if relation_names and len(attempted) < policy.maximum_provider_calls:
            dataset_name = relation_names[0]
            relation_provider = self._relation_provider(academic_order)
            relation_query = f'"{dataset_name}" dataset benchmark baseline method comparison'
            bundle = await self._service.retrieve(
                self._build_plan(
                    query,
                    [relation_provider],
                    lane_suffix=f"dataset-{dataset_name.casefold()}",
                    query_text=relation_query,
                    purpose="benchmark_dataset",
                    priority=75,
                )
            )
            attempted.append(f"{relation_provider}:dataset_relation")
            provider_results.extend(bundle.provider_results)
            for paper in bundle.papers:
                if self._passes_relation_relevance(paper, dataset_name=dataset_name):
                    relation_paper_ids.add(paper.paper_id)
                    dataset_links.setdefault(paper.paper_id, set()).add(dataset_name)
            self._merge_papers(papers_by_id, bundle.papers)
''',
        '''        if relation_names and len(attempted) < policy.maximum_provider_calls:
            dataset_name = relation_names[0]
            relation_query = f'"{dataset_name}" dataset benchmark baseline method comparison'
            for relation_provider in self._relation_providers(academic_order):
                if len(attempted) >= policy.maximum_provider_calls:
                    break
                bundle = await self._service.retrieve(
                    self._build_plan(
                        query,
                        [relation_provider],
                        lane_suffix=(
                            f"dataset-{dataset_name.casefold()}-{relation_provider}"
                        ),
                        query_text=relation_query,
                        purpose="benchmark_dataset",
                        priority=75,
                    )
                )
                attempted.append(f"{relation_provider}:dataset_relation")
                provider_results.extend(bundle.provider_results)
                relation_found = False
                for paper in bundle.papers:
                    if self._passes_relation_relevance(
                        paper,
                        dataset_name=dataset_name,
                    ):
                        relation_found = True
                        relation_paper_ids.add(paper.paper_id)
                        dataset_links.setdefault(paper.paper_id, set()).add(dataset_name)
                self._merge_papers(papers_by_id, bundle.papers)
                if relation_found:
                    break
''',
        "multi-provider dataset relation fallback",
    )
    replace_once(
        ADAPTER,
        '''    @staticmethod
    def _relation_provider(academic_order: tuple[str, ...]) -> str:
        for preferred in ("semantic_scholar", "openalex", "arxiv"):
            if preferred in academic_order:
                return preferred
        return academic_order[0]
''',
        '''    @staticmethod
    def _relation_providers(academic_order: tuple[str, ...]) -> tuple[str, ...]:
        preferred_order = ("openalex", "arxiv", "semantic_scholar")
        return tuple(
            provider
            for provider in preferred_order
            if provider in academic_order
        )
''',
        "relation provider order",
    )
    append_once(
        TEST,
        "test_relation_providers_defer_rate_limited_source",
        '''


def test_relation_providers_defer_rate_limited_source() -> None:
    providers = LiteratureSearchAdapter._relation_providers(
        ("semantic_scholar", "openalex", "arxiv")
    )
    assert providers == ("openalex", "arxiv", "semantic_scholar")


def test_relation_provider_order_respects_configured_availability() -> None:
    providers = LiteratureSearchAdapter._relation_providers(("arxiv", "semantic_scholar"))
    assert providers == ("arxiv", "semantic_scholar")
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
