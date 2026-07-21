from __future__ import annotations

from pathlib import Path


SCORER = Path("scripts/score_academic_tailoring_retrieval_v1.py")
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


def main() -> int:
    replace_once(
        SCORER,
        '    identity_text = _normalize("\n".join(_identity_values(item)))\n',
        '    identity_text = _normalize("\\n".join(_identity_values(item)))\n',
        "identity newline escape",
    )
    replace_once(
        ADAPTER,
        '''def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in _DATASET_CONTEXT.finditer(query):
        name = match.group("name").strip(".,;:()[]{}")
        if name.casefold() not in _DATASET_GENERIC and name not in names:
            names.append(name)
    for token in re.findall(r"\\b[A-Za-z][A-Za-z0-9._-]{2,}\\b", query):
        compact = token.replace("-", "").replace("_", "").replace(".", "")
        distinctive = any(char.isdigit() for char in compact) or token.isupper() or (
            any(char.isupper() for char in token[1:]) and any(char.islower() for char in token)
        )
        if distinctive and token.casefold() not in _DATASET_GENERIC and token not in names:
            names.append(token)
    return tuple(names)
''',
        '''def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\\s*(?:/|,|and)\\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\\s+(?:datasets?|benchmarks?|corpus|corpora)\\b",
        re.IGNORECASE,
    )
    for match in context.finditer(query):
        for raw_name in re.split(r"\\s*(?:/|,|and)\\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}")
            if name.casefold() not in _DATASET_GENERIC and name not in names:
                names.append(name)
    return tuple(names)
''',
        "explicit dataset context extraction",
    )
    replace_once(
        ADAPTER,
        '                            f"Dataset {dataset_name!r} is explicitly named in the title or abstract "\n',
        '                            f"Dataset {dataset_name!r} is explicitly named in the title "\n'
        '                            "or abstract "\n',
        "dataset snippet wrapping",
    )
    replace_once(
        METHOD,
        '            "declared baseline identity unresolved; do not implement until the exact paper is verified"\n',
        '            (\n'
        '                "declared baseline identity unresolved; do not implement until the exact "\n'
        '                "paper is verified"\n'
        '            )\n',
        "unresolved baseline wrapping",
    )
    replace_once(
        ADAPTER_TEST,
        '        "Dynamic Training Strategies for Domain Generalization in Self-Supervised Anomaly Sound Detection",\n',
        '        "Dynamic Training Strategies for Domain Generalization in Self-Supervised "\n'
        '        "Anomaly Sound Detection",\n',
        "adapter test title wrapping",
    )
    replace_once(
        METHOD_TEST,
        '        ["PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition [declared role: baseline]"],\n',
        '        [\n'
        '            "PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern "\n'
        '            "Recognition [declared role: baseline]"\n'
        '        ],\n',
        "method test title wrapping",
    )
    append_once(
        ADAPTER_TEST,
        "test_model_name_is_not_promoted_to_dataset_without_dataset_context",
        '''


def test_model_name_is_not_promoted_to_dataset_without_dataset_context() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-model-dataset",
        gap_id="g-model-dataset",
        query="Evaluate PANNs on the MIMII dataset under low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper(
            "PANNs: Large-Scale Pretrained Audio Neural Networks",
            "The PANNs model is evaluated on the MIMII dataset.",
        ),
        False,
    )
    dataset_titles = [item.title for item in candidates if item.source_type == "dataset"]
    assert dataset_titles == ["MIMII"]
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
