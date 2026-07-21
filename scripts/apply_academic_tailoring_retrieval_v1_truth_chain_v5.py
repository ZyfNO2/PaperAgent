from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/paperagent/literature/adapter.py")
METHOD = Path("src/paperagent/method_design_draft.py")
SCORER = Path("scripts/score_academic_tailoring_retrieval_v1.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
METHOD_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")
SCORER_TEST = Path("tests/evals/test_academic_tailoring_retrieval_v1_scorer.py")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old in source:
        return source.replace(old, new, 1)
    if new in source:
        return source
    raise RuntimeError(f"missing replacement marker: {label}")


def patch_adapter() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '        academic = [*(source_preferences or ["openalex", "semantic_scholar"])]\n',
        '        academic = [*(source_preferences or ["openalex", "semantic_scholar", "arxiv"])]\n',
        "default academic sources",
    )

    helpers = r'''

_QUOTED_TITLE = re.compile(r'["“](?P<title>[^"”]{8,})["”]')
_DATASET_CONTEXT = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9._-]{2,})\s+(?:dataset|benchmark|corpus)\b",
    re.IGNORECASE,
)
_DATASET_GENERIC = frozenset(
    {
        "audio",
        "public",
        "training",
        "test",
        "evaluation",
        "forecasting",
        "anomaly",
        "detection",
        "classification",
        "dataset",
        "benchmark",
        "corpus",
    }
)


def _quoted_title(query: str) -> str | None:
    match = _QUOTED_TITLE.search(query)
    if match is None:
        return None
    title = match.group("title").strip()
    return title or None


def _identity_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _exact_title_match(left: str, right: str) -> bool:
    left_tokens = _identity_tokens(left)
    right_tokens = _identity_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if len(left_tokens) == 1 and len(left_tokens[0]) >= 3 and left_tokens[0] == right_tokens[0]:
        return True
    if len(right_tokens) == 1 and len(right_tokens[0]) >= 3 and right_tokens[0] == left_tokens[0]:
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = left_set & right_set
    union = left_set | right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.9 and length_ratio >= 0.8


def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in _DATASET_CONTEXT.finditer(query):
        name = match.group("name").strip(".,;:()[]{}")
        if name.casefold() not in _DATASET_GENERIC and name not in names:
            names.append(name)
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9._-]{2,}\b", query):
        compact = token.replace("-", "").replace("_", "").replace(".", "")
        distinctive = any(char.isdigit() for char in compact) or token.isupper() or (
            any(char.isupper() for char in token[1:]) and any(char.islower() for char in token)
        )
        if distinctive and token.casefold() not in _DATASET_GENERIC and token not in names:
            names.append(token)
    return tuple(names)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    text = f"{paper.canonical_title}\n{paper.abstract or ''}".casefold()
    return tuple(name for name in _dataset_names_from_query(query) if name.casefold() in text)
'''
    marker = "\n\nclass LiteratureSearchAdapter:\n"
    if "def _quoted_title(" not in source:
        source = source.replace(marker, helpers + marker, 1)

    source = replace_once(
        source,
        "        policy = review_search_query(query)\n",
        "        policy = review_search_query(query)\n        required_title = _quoted_title(query.query)\n",
        "required title extraction",
    )
    source = replace_once(
        source,
        "            if self._has_sufficient_academic_evidence(papers_by_id.values(), policy):\n",
        "            if self._has_sufficient_academic_evidence(\n                papers_by_id.values(), policy, required_title=required_title\n            ):\n",
        "exact title sufficiency call",
    )
    source = replace_once(
        source,
        """        filtered = [
            paper for paper in papers_by_id.values() if self._passes_return_relevance(paper, policy)
        ]
""",
        """        filtered = [
            paper for paper in papers_by_id.values() if self._passes_return_relevance(paper, policy)
        ]
        if required_title is not None:
            filtered = [
                paper
                for paper in filtered
                if _exact_title_match(paper.canonical_title, required_title)
            ]
""",
        "exact title result filter",
    )
    source = replace_once(
        source,
        """    @staticmethod
    def _has_sufficient_academic_evidence(
        papers: Iterable[PaperRecord],
        policy: SearchSourcePolicy,
    ) -> bool:
        relevant = sum(
            paper.verification_status == "verified"
            and paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in papers
        )
        return relevant >= policy.minimum_relevant_results
""",
        """    @staticmethod
    def _has_sufficient_academic_evidence(
        papers: Iterable[PaperRecord],
        policy: SearchSourcePolicy,
        *,
        required_title: str | None = None,
    ) -> bool:
        paper_list = list(papers)
        if required_title is not None:
            return any(
                paper.verification_status == "verified"
                and _exact_title_match(paper.canonical_title, required_title)
                for paper in paper_list
            )
        relevant = sum(
            paper.verification_status == "verified"
            and paper.rank_features is not None
            and paper.rank_features.relevance >= policy.minimum_relevance
            and paper.rank_features.score >= policy.minimum_rank_score
            for paper in paper_list
        )
        return relevant >= policy.minimum_relevant_results
""",
        "exact title sufficiency implementation",
    )

    old_candidates = '''        candidates = [self._candidate(query, paper, fallback_used)]
        if paper.verification_status != "verified":
            return candidates
        if not {"repository", "web"}.intersection(query.source_types):
            return candidates
        providers = sorted({record.provider for record in paper.source_records})
        score = paper.rank_features.score if paper.rank_features else 0.0
        relevance = paper.rank_features.relevance if paper.rank_features else 0.0
        for url, title in _normalized_github_repository_urls(paper):
'''
    new_candidates = '''        candidates = [self._candidate(query, paper, fallback_used)]
        if paper.verification_status != "verified":
            return candidates
        providers = sorted({record.provider for record in paper.source_records})
        score = paper.rank_features.score if paper.rank_features else 0.0
        relevance = paper.rank_features.relevance if paper.rank_features else 0.0
        if {"repository", "web"}.intersection(query.source_types):
            for url, title in _normalized_github_repository_urls(paper):
'''
    source = replace_once(source, old_candidates, new_candidates, "candidate expansion header")
    # Indent the existing repository append block under the new conditional.
    repo_start = source.index("            for url, title in _normalized_github_repository_urls(paper):")
    repo_end = source.index("        return candidates", repo_start)
    repo_block = source[repo_start:repo_end]
    lines = repo_block.splitlines()
    if lines and any(line.startswith("            digest =") for line in lines):
        adjusted = [lines[0]] + ["    " + line for line in lines[1:]]
        repo_block = "\n".join(adjusted) + "\n"
        source = source[:repo_start] + repo_block + source[repo_end:]

    dataset_block = r'''        if "dataset" in query.source_types:
            parent_locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            for dataset_name in _paper_dataset_mentions(query.query, paper):
                identity = f"{dataset_name.casefold()}|{paper.paper_id}"
                digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
                candidates.append(
                    SearchCandidate(
                        candidate_id=f"dataset-{digest}",
                        query_id=query.query_id,
                        gap_id=query.gap_id,
                        source_type="dataset",
                        title=dataset_name,
                        locator=parent_locator,
                        snippet=(
                            f"Dataset {dataset_name!r} is explicitly named in the title or abstract "
                            f"of the verified paper {paper.canonical_title!r}. This verifies the "
                            "dataset mention, not an official download page or split manifest."
                        ),
                        provider=self.provider_name,
                        metadata={
                            "query_text": query.query,
                            "verification_status": "verified",
                            "providers": ",".join(providers),
                            "provider_classes": "academic-linked-dataset-mention",
                            "source_kind": "dataset",
                            "rank_score": f"{score:.6f}",
                            "relevance_score": f"{relevance:.6f}",
                            "relation": "dataset_named_in_verified_paper",
                            "parent_paper_id": paper.paper_id,
                            "parent_paper_title": paper.canonical_title,
                            "dataset_ref": dataset_name,
                            "fallback_used": "true" if fallback_used else "false",
                            "web_supplement": "false",
                        },
                    )
                )
'''
    return_marker = "        return candidates\n\n    def _candidate(\n"
    if "dataset_named_in_verified_paper" not in source:
        source = source.replace(return_marker, dataset_block + "        return candidates\n\n    def _candidate(\n", 1)
    ADAPTER.write_text(source, encoding="utf-8")


def patch_method() -> None:
    source = METHOD.read_text(encoding="utf-8")
    old = '''def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    declared_titles = _declared_baseline_titles(references)
    for declared_title in declared_titles:
        for item in candidates:
            if item.source_type == "paper" and _titles_equivalent(item.title, declared_title):
                return item
    return candidates[0]
'''
    new = '''def _select_declared_baseline_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    declared_titles = _declared_baseline_titles(references)
    for declared_title in declared_titles:
        for item in candidates:
            if item.source_type == "paper" and _titles_equivalent(item.title, declared_title):
                return item
    return None


def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    return _select_declared_baseline_evidence(references, candidates) or candidates[0]


def _select_dataset_evidence(question: str, candidates: tuple[EvidenceItem, ...]) -> EvidenceItem | None:
    datasets = tuple(item for item in candidates if item.source_type == "dataset")
    for item in datasets:
        if item.title.casefold() in question.casefold():
            return item
    return datasets[0] if datasets else None
'''
    source = replace_once(source, old, new, "method evidence selectors")

    source = replace_once(
        source,
        '''    primary = _select_primary_evidence(
        list(request.user_material_refs),
        attributed if attributed else accepted,
    )
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
''',
        '''    method_evidence = attributed if attributed else accepted
    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    )
    primary = baseline_evidence or method_evidence[0]
    dataset_evidence = _select_dataset_evidence(request.question, accepted)
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    if grounded_dataset is None and dataset_evidence is not None:
        grounded_dataset = dataset_evidence.title
''',
        "method evidence assignment",
    )
    source = replace_once(
        source,
        '''    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_name = (
        "unresolved task-matched baseline selected from accepted review evidence"
        if review_primary
        else primary.title
    )
''',
        '''    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_unresolved = bool(declared_baseline_titles and baseline_evidence is None)
    baseline_name = (
        declared_baseline_titles[0]
        if baseline_unresolved
        else (
            "unresolved task-matched baseline selected from accepted review evidence"
            if review_primary
            else primary.title
        )
    )
    baseline_source_evidence_id = (
        baseline_evidence.evidence_id
        if baseline_evidence is not None
        else (None if baseline_unresolved else primary.evidence_id)
    )
''',
        "baseline unresolved behavior",
    )
    source = replace_once(
        source,
        '''        version_or_commit=(
            "user-declared frozen implementation; preserve the exact version or commit"
            if readiness_confirmed
            else (
                f"review source {primary.stable_identifier}; implementation baseline unresolved"
                if review_primary
                else (
                    f"published source {primary.stable_identifier}; "
                    "implementation commit unresolved"
                )
            )
        ),
        source_evidence_id=primary.evidence_id,
''',
        '''        version_or_commit=(
            "declared baseline identity unresolved; do not implement until the exact paper is verified"
            if baseline_unresolved
            else (
                "user-declared frozen implementation; preserve the exact version or commit"
                if readiness_confirmed
                else (
                    f"review source {primary.stable_identifier}; implementation baseline unresolved"
                    if review_primary
                    else (
                        f"published source {primary.stable_identifier}; "
                        "implementation commit unresolved"
                    )
                )
            )
        ),
        source_evidence_id=baseline_source_evidence_id,
''',
        "baseline card source",
    )
    source = replace_once(
        source,
        "        source_evidence_id=primary.evidence_id,\n        license=_metadata_text(primary.metadata, \"license\"),\n        dataset=dataset,\n",
        "        source_evidence_id=baseline_source_evidence_id,\n        license=_metadata_text(primary.metadata, \"license\"),\n        dataset=dataset,\n",
        "baseline duplicate source safety",
    ) if source.count("source_evidence_id=primary.evidence_id,\n        license=_metadata_text(primary.metadata") > 1 else source
    source = replace_once(
        source,
        "    source_evidence_id: str,\n",
        "    source_evidence_id: str | None,\n",
        "optional experiment evidence",
    )
    # Baseline experiment may be unresolved; module/full arms remain bound to method evidence.
    source = replace_once(
        source,
        '''            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="establish a reproducible task-matched baseline under frozen settings",
''',
        '''            source_evidence_id=baseline_source_evidence_id,
            comparator=baseline_name,
            purpose="establish a reproducible task-matched baseline under frozen settings",
''',
        "baseline experiment source",
    )
    METHOD.write_text(source, encoding="utf-8")


def patch_scorer() -> None:
    source = SCORER.read_text(encoding="utf-8")
    old = '''def _title_matches(title: str, haystack: str) -> bool:
    normalized = _normalize(title)
    if normalized and normalized in haystack:
        return True
    tokens = set(normalized.split())
    if len(tokens) < 3:
        return False
    return len(tokens & set(haystack.split())) / len(tokens) >= 0.8


def _asset_matches(asset: dict[str, Any], state_text: str) -> bool:
    title = asset.get("title")
    if isinstance(title, str) and title.strip() and _title_matches(title, state_text):
        return True
    for key in ("doi", "arxiv", "url"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            normalized = _normalize(value)
            if normalized and normalized in state_text:
                return True
    return False
'''
    new = '''def _identity_values(item: dict[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata", {})
    values = [item.get("title"), item.get("locator")]
    if isinstance(metadata, dict):
        values.extend(
            metadata.get(key)
            for key in (
                "doi",
                "arxiv_id",
                "repository_ref",
                "dataset_ref",
                "canonical_url",
            )
        )
    return tuple(value for value in values if isinstance(value, str) and value.strip())


def _strong_dataset_identifiers(value: str) -> set[str]:
    identifiers: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9._-]{2,}", value):
        compact = re.sub(r"[^A-Za-z0-9]+", "", token)
        if any(char.isdigit() for char in compact) or token.isupper() or (
            any(char.isupper() for char in token[1:]) and any(char.islower() for char in token)
        ):
            identifiers.add(compact.casefold())
    return identifiers


def _dataset_titles_related(left: str, right: str) -> bool:
    if _titles_related(left, right):
        return True
    return bool(_strong_dataset_identifiers(left) & _strong_dataset_identifiers(right))


def _asset_matches_item(asset: dict[str, Any], item: dict[str, Any]) -> bool:
    title = asset.get("title")
    item_title = item.get("title")
    kind = str(asset.get("kind", ""))
    if isinstance(title, str) and title.strip() and isinstance(item_title, str):
        if kind == "dataset":
            if _dataset_titles_related(title, item_title):
                return True
        elif _titles_related(title, item_title):
            return True
    identity_text = _normalize("\n".join(_identity_values(item)))
    for key in ("doi", "arxiv", "url"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            normalized = _normalize(value)
            if normalized and normalized in identity_text:
                return True
    return False
'''
    source = replace_once(source, old, new, "identity-only asset matching")
    source = replace_once(
        source,
        '''def _accepted_asset_matches(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
    accepted_text = _normalize("\n".join(_flatten_strings(items)))
    return sum(_asset_matches(asset, accepted_text) for asset in assets)
''',
        '''def _accepted_asset_matches(assets: list[dict[str, Any]], items: list[dict[str, Any]]) -> int:
    return sum(any(_asset_matches_item(asset, item) for item in items) for asset in assets)


def _dataset_asset_score(
    assets: list[dict[str, Any]], items: list[dict[str, Any]]
) -> int:
    if not assets:
        return 7 if items else 0
    total = 0
    for asset in assets:
        matching = [item for item in items if _asset_matches_item(asset, item)]
        if not matching:
            continue
        quality = 0
        for item in matching:
            metadata = item.get("metadata", {})
            relation = metadata.get("relation") if isinstance(metadata, dict) else None
            quality = max(quality, 4 if relation == "dataset_named_in_verified_paper" else 7)
        total += quality
    return round(total / len(assets))
''',
        "dataset evidence quality",
    )
    source = replace_once(
        source,
        '''    dataset_score = 0
    if dataset_assets:
        dataset_score += round(7 * matched_datasets / len(dataset_assets))
    elif accepted_datasets:
        dataset_score += 7
''',
        '''    dataset_score = _dataset_asset_score(dataset_assets, accepted_datasets)
''',
        "dataset scoring",
    )
    SCORER.write_text(source, encoding="utf-8")


def write_tests() -> None:
    ADAPTER_TEST.write_text(
        r'''from __future__ import annotations

from types import SimpleNamespace

from paperagent.literature.adapter import (
    LiteratureSearchAdapter,
    _exact_title_match,
    _quoted_title,
)
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import PaperRecord, RankFeatures, SourceRecord


def _paper(title: str, abstract: str = "") -> PaperRecord:
    return PaperRecord(
        paper_id="paper-test",
        canonical_title=title,
        abstract=abstract,
        doi="10.1000/test",
        urls=[],
        source_records=[SourceRecord(provider="openalex", provider_record_id="x", request_id="r")],
        verification_status="verified",
        rank_features=RankFeatures(
            relevance=1.0,
            gap_coverage=1.0,
            metadata_verification=1.0,
            recency_fit=1.0,
            diversity=1.0,
            citation_tiebreaker=1.0,
            score=1.0,
        ),
    )


def test_quoted_identity_requires_exact_title_before_provider_stop() -> None:
    required = _quoted_title('"PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition"')
    assert required is not None
    assert _exact_title_match(required, required)
    assert not _exact_title_match(
        "Dynamic Training Strategies for Domain Generalization in Self-Supervised Anomaly Sound Detection",
        required,
    )


def test_dataset_candidate_is_explicitly_linked_to_verified_paper_mention() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q",
        gap_id="g",
        query="MIMII dataset evaluation protocol low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper("Industrial sound evaluation", "Experiments use the MIMII dataset under noise."),
        False,
    )
    datasets = [item for item in candidates if item.source_type == "dataset"]
    assert len(datasets) == 1
    assert datasets[0].title == "MIMII"
    assert datasets[0].metadata["relation"] == "dataset_named_in_verified_paper"
''',
        encoding="utf-8",
    )

    method_tests = METHOD_TEST.read_text(encoding="utf-8")
    method_tests = method_tests.replace(
        "from paperagent.method_design_draft import _select_primary_evidence\n",
        "from paperagent.method_design_draft import (\n    _select_dataset_evidence,\n    _select_declared_baseline_evidence,\n    _select_primary_evidence,\n)\n",
    )
    addition = r'''


def test_missing_declared_baseline_does_not_substitute_neighbor_paper() -> None:
    neighbor = _item("neighbor", "A Different Paper About the Same Task")
    selected = _select_declared_baseline_evidence(
        ["PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition [declared role: baseline]"],
        (neighbor,),
    )
    assert selected is None


def test_dataset_evidence_prefers_name_present_in_user_question() -> None:
    unrelated = _item("other", "OtherData")
    target = unrelated.model_copy(
        update={"evidence_id": "mimii", "source_type": "dataset", "title": "MIMII"}
    )
    selected = _select_dataset_evidence("Evaluate PANNs on MIMII under low SNR", (unrelated, target))
    assert selected is not None
    assert selected.evidence_id == "mimii"
'''
    if "test_missing_declared_baseline_does_not_substitute_neighbor_paper" not in method_tests:
        method_tests += addition
    METHOD_TEST.write_text(method_tests, encoding="utf-8")

    scorer_tests = SCORER_TEST.read_text(encoding="utf-8")
    scorer_tests = scorer_tests.replace(
        "_accepted_verified_items = _SCORER._accepted_verified_items\n",
        "_accepted_asset_matches = _SCORER._accepted_asset_matches\n_accepted_verified_items = _SCORER._accepted_verified_items\n_dataset_asset_score = _SCORER._dataset_asset_score\n",
    )
    addition = r'''


def test_query_text_cannot_impersonate_missing_paper_identity() -> None:
    assets = [{"kind": "paper", "title": "USAD: UnSupervised Anomaly Detection on Multivariate Time Series"}]
    items = [
        {
            "source_type": "paper",
            "title": "An Efficient Method for Detecting Abnormal Electricity Behavior",
            "locator": "doi:10.1000/wrong",
            "metadata": {
                "query_text": '"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"'
            },
        }
    ]
    assert _accepted_asset_matches(assets, items) == 0


def test_dataset_mention_scores_partial_not_official_identity_credit() -> None:
    assets = [{"kind": "dataset", "title": "MIMII dataset"}]
    items = [
        {
            "source_type": "dataset",
            "title": "MIMII",
            "locator": "doi:10.1000/paper",
            "metadata": {"relation": "dataset_named_in_verified_paper", "dataset_ref": "MIMII"},
        }
    ]
    assert _accepted_asset_matches(assets, items) == 1
    assert _dataset_asset_score(assets, items) == 4
'''
    if "test_query_text_cannot_impersonate_missing_paper_identity" not in scorer_tests:
        scorer_tests += addition
    SCORER_TEST.write_text(scorer_tests, encoding="utf-8")


def main() -> int:
    patch_adapter()
    patch_method()
    patch_scorer()
    write_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
