from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/paperagent/literature/adapter.py")
METHOD = Path("src/paperagent/method_design_draft.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
METHOD_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")


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


def patch_adapter() -> None:
    replace_once(
        ADAPTER,
        '''_DATASET_GENERIC = frozenset(
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
''',
        '''_DATASET_GENERIC = frozenset(
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
        "available",
        "specific",
        "large-scale",
        "self-built",
        "latest",
        "this",
        "that",
        "image",
        "images",
        "challenge",
    }
)
_DATASET_MODEL_TOKENS = frozenset(
    {
        "bert",
        "cnn",
        "detr",
        "gat",
        "gcn",
        "gnn",
        "gru",
        "llm",
        "lora",
        "lstm",
        "mlp",
        "rnn",
        "transformer",
        "vit",
        "yolo",
    }
)
''',
        "dataset generic identifiers",
    )
    replace_once(
        ADAPTER,
        '''def _dataset_names_from_text(text: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\\s*(?:/|,|and)\\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\\s+(?:datasets?|benchmarks?|corpus|corpora)\\b",
        re.IGNORECASE,
    )
    for match in context.finditer(text):
        for raw_name in re.split(r"\\s*(?:/|,|and)\\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}")
            if name.casefold() not in _DATASET_GENERIC and name not in names:
                names.append(name)
    return tuple(names)


def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    return _dataset_names_from_text(query)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    paper_text = f"{paper.canonical_title}\\n{paper.abstract or ''}"
    normalized = paper_text.casefold()
    names = list(_dataset_names_from_text(paper_text))
    for name in _dataset_names_from_query(query):
        if name.casefold() in normalized and name not in names:
            names.append(name)
    return tuple(names)


def _dataset_relation_names(
    query: str,
    papers: Iterable[PaperRecord],
) -> tuple[str, ...]:
    names = list(_dataset_names_from_query(query))
    for paper in papers:
        for name in _dataset_names_from_text(f"{paper.canonical_title}\\n{paper.abstract or ''}"):
            if name not in names:
                names.append(name)
    return tuple(names)
''',
        '''def _looks_like_dataset_name(value: str) -> bool:
    name = value.strip(".,;:()[]{}\"'")
    normalized = name.casefold()
    compact = re.sub(r"[^A-Za-z0-9]", "", name)
    if (
        len(compact) < 3
        or len(compact) > 40
        or normalized in _DATASET_GENERIC
        or normalized in _DATASET_MODEL_TOKENS
    ):
        return False
    if any(char.isdigit() for char in compact):
        return True
    if compact.isupper():
        return True
    return (
        any(char.isupper() for char in compact[1:])
        and any(char.islower() for char in compact)
    )


def _explicit_dataset_names_from_text(text: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\\s*(?:/|,|and)\\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\\s+(?:datasets?|benchmarks?|corpus|corpora)\\b",
        re.IGNORECASE,
    )
    for match in context.finditer(text):
        for raw_name in re.split(r"\\s*(?:/|,|and)\\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}\"'")
            if _looks_like_dataset_name(name) and name not in names:
                names.append(name)
    return tuple(names)


def _distinctive_dataset_tokens(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for token in re.findall(r"\\b[A-Za-z][A-Za-z0-9._-]{2,}\\b", text):
        name = token.strip(".,;:()[]{}\"'")
        if _looks_like_dataset_name(name) and name not in names:
            names.append(name)
    return tuple(names)


def _dataset_names_from_text(text: str) -> tuple[str, ...]:
    return _explicit_dataset_names_from_text(text)


def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names = list(_explicit_dataset_names_from_text(query))
    for name in _distinctive_dataset_tokens(query):
        if name not in names:
            names.append(name)
    return tuple(names)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    paper_text = f"{paper.canonical_title}\\n{paper.abstract or ''}"
    normalized = paper_text.casefold()
    names = list(_explicit_dataset_names_from_text(paper_text))
    for name in _explicit_dataset_names_from_text(query):
        if name.casefold() in normalized and name not in names:
            names.append(name)
    return tuple(names)


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
    names = [
        name
        for name in _dataset_names_from_query(query)
        if name.casefold() not in blocked
    ]
    for paper in paper_list:
        for name in _explicit_dataset_names_from_text(
            f"{paper.canonical_title}\\n{paper.abstract or ''}"
        ):
            if name not in names:
                names.append(name)
    return tuple(names)
''',
        "precise dataset entity extraction",
    )
    replace_once(
        ADAPTER,
        '''        relation_names = _dataset_relation_names(query.query, papers_by_id.values())
        if relation_names:
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
                if self._passes_relation_relevance(paper):
                    relation_paper_ids.add(paper.paper_id)
                    dataset_links.setdefault(paper.paper_id, set()).add(dataset_name)
            self._merge_papers(papers_by_id, bundle.papers)
''',
        '''        relation_names = (
            _dataset_relation_names(query.query, papers_by_id.values())
            if "dataset" in query.source_types
            else ()
        )
        if relation_names and len(attempted) < policy.maximum_provider_calls:
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
        "bounded dataset relation expansion",
    )
    replace_once(
        ADAPTER,
        '''    @staticmethod
    def _passes_relation_relevance(paper: PaperRecord) -> bool:
        features = paper.rank_features
        return (
            paper.verification_status == "verified"
            and features is not None
            and features.relevance >= 0.20
            and features.score >= 0.40
        )
''',
        '''    @staticmethod
    def _passes_relation_relevance(
        paper: PaperRecord,
        *,
        dataset_name: str,
    ) -> bool:
        if paper.verification_status != "verified":
            return False
        text = f"{paper.canonical_title}\\n{paper.abstract or ''}".casefold()
        if dataset_name.casefold() in text:
            return True
        features = paper.rank_features
        return (
            features is not None
            and features.relevance >= 0.32
            and features.score >= 0.55
        )
''',
        "dataset-aware relation relevance",
    )


def patch_method() -> None:
    replace_once(
        METHOD,
        '''def _select_dataset_evidence(
    question: str, candidates: tuple[EvidenceItem, ...]
) -> EvidenceItem | None:
    datasets = tuple(item for item in candidates if item.source_type == "dataset")
    for item in datasets:
        if item.title.casefold() in question.casefold():
            return item
    return datasets[0] if datasets else None
''',
        '''def _dataset_evidence_rank(item: EvidenceItem) -> tuple[int, float, str]:
    relation = item.metadata.get("relation", "")
    relation_rank = {
        "dataset_linked_by_focused_retrieval": 2,
        "dataset_named_in_verified_paper": 1,
    }.get(relation, 0)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (relation_rank, rank_score, item.evidence_id)


def _select_dataset_evidence(
    question: str, candidates: tuple[EvidenceItem, ...]
) -> EvidenceItem | None:
    datasets = tuple(item for item in candidates if item.source_type == "dataset")
    normalized_question = question.casefold()
    explicit = tuple(
        item
        for item in datasets
        if re.search(
            rf"(?<![a-z0-9]){re.escape(item.title.casefold())}(?![a-z0-9])",
            normalized_question,
        )
    )
    if explicit:
        return max(explicit, key=_dataset_evidence_rank)
    linked = tuple(
        item
        for item in datasets
        if item.metadata.get("relation") == "dataset_linked_by_focused_retrieval"
    )
    if linked:
        return max(linked, key=_dataset_evidence_rank)
    return None
''',
        "evidence-grounded dataset selection",
    )


def patch_tests() -> None:
    replace_once(
        ADAPTER_TEST,
        '''    _dataset_relation_names,
    _exact_title_match,
    _quoted_title,
)
''',
        '''    _dataset_names_from_text,
    _dataset_relation_names,
    _exact_title_match,
    _looks_like_dataset_name,
    _quoted_title,
)
''',
        "dataset helper test imports",
    )
    append_once(
        ADAPTER_TEST,
        "test_dataset_entity_precision_rejects_descriptive_words",
        '''


def test_dataset_entity_precision_rejects_descriptive_words() -> None:
    text = (
        "We use a specific dataset, a large-scale dataset, and this dataset for evaluation. "
        "Results are also reported on the AudioSet dataset and MIMII benchmark."
    )
    assert _dataset_names_from_text(text) == ("AudioSet", "MIMII")
    assert not _looks_like_dataset_name("specific")
    assert not _looks_like_dataset_name("large-scale")
    assert _looks_like_dataset_name("CLINC150")
    assert _looks_like_dataset_name("SWaT")


def test_dataset_relation_query_keeps_dataset_anchor_not_model_title() -> None:
    names = _dataset_relation_names(
        "PANNs pretrained audio baseline performance MIMII dataset",
        (_paper("PANNs: Large-Scale Pretrained Audio Neural Networks"),),
    )
    assert names == ("MIMII",)


def test_dataset_relation_relevance_accepts_verified_dataset_title() -> None:
    paper = _paper("MIMII Dataset: Sound Dataset for Machine Investigation")
    paper = paper.model_copy(
        update={
            "rank_features": paper.rank_features.model_copy(
                update={"relevance": 0.01, "score": 0.01}
            )
        }
    )
    assert LiteratureSearchAdapter._passes_relation_relevance(
        paper,
        dataset_name="MIMII",
    )
''',
    )
    replace_once(
        METHOD_TEST,
        '''    _dataset_plan_value,
    _select_dataset_evidence,
''',
        '''    _dataset_plan_value,
    _select_dataset_evidence,
''',
        "method dataset test import stability",
    )
    append_once(
        METHOD_TEST,
        "test_dataset_selection_prefers_explicit_question_anchor",
        '''


def test_dataset_selection_prefers_explicit_question_anchor() -> None:
    audio_set = _item(
        "audioset",
        "AudioSet",
        metadata={
            "relation": "dataset_named_in_verified_paper",
            "rank_score": "0.95",
        },
    ).model_copy(update={"source_type": "dataset"})
    mimii = _item(
        "mimii",
        "MIMII",
        metadata={
            "relation": "dataset_linked_by_focused_retrieval",
            "rank_score": "0.60",
        },
    ).model_copy(update={"source_type": "dataset"})
    selected = _select_dataset_evidence(
        "Evaluate the method on MIMII under low SNR",
        (audio_set, mimii),
    )
    assert selected is not None
    assert selected.title == "MIMII"


def test_dataset_selection_does_not_promote_arbitrary_paper_mention() -> None:
    audio_set = _item(
        "audioset",
        "AudioSet",
        metadata={
            "relation": "dataset_named_in_verified_paper",
            "rank_score": "0.95",
        },
    ).model_copy(update={"source_type": "dataset"})
    selected = _select_dataset_evidence(
        "Design a method for a proprietary rare sensor task",
        (audio_set,),
    )
    assert selected is None
''',
    )


def main() -> int:
    patch_adapter()
    patch_method()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
