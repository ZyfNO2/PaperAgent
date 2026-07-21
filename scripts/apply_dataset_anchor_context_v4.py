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
        '''        "challenge",
    }
)
_DATASET_MODEL_TOKENS = frozenset(
''',
        '''        "challenge",
        "auc",
        "auprc",
        "auroc",
        "eer",
        "f1",
        "flops",
        "fps",
        "hr",
        "iou",
        "mae",
        "map",
        "mrr",
        "mse",
        "ndcg",
        "ood",
        "rmse",
        "snr",
        "sota",
    }
)
_DATASET_MODEL_TOKENS = frozenset(
''',
        "dataset metric exclusions",
    )
    replace_once(
        ADAPTER,
        '''def _distinctive_dataset_tokens(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for token in re.findall(r"\\b[A-Za-z][A-Za-z0-9._-]{2,}\\b", text):
        name = token.strip(".,;:()[]{}")
        if _looks_like_dataset_name(name) and name not in names:
            names.append(name)
    return tuple(names)
''',
        '''def _distinctive_dataset_tokens(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for token in re.findall(r"\\b[A-Za-z][A-Za-z0-9._-]{2,}\\b", text):
        name = token.strip(".,;:()[]{}")
        compact = re.sub(r"[^A-Za-z0-9]", "", name)
        identity_like = compact.isupper() or any(char.isdigit() for char in compact)
        if identity_like and _looks_like_dataset_name(name) and name not in names:
            names.append(name)
    return tuple(names)
''',
        "context-free dataset token restriction",
    )
    append_once(
        TEST,
        "test_context_free_dataset_tokens_reject_models_and_metrics",
        '''


def test_context_free_dataset_tokens_reject_models_and_metrics() -> None:
    assert _dataset_relation_names(
        "PatchTST missing data forecasting SNR AUC F1",
        (_paper("A Time Series is Worth 64 Words"),),
    ) == ()
    assert _dataset_relation_names(
        "GraphSAGE PPI inductive node classification Micro-F1",
        (_paper("Inductive Representation Learning on Large Graphs"),),
    ) == ("PPI",)
    assert _dataset_relation_names(
        "DeepGO protein function prediction low annotation coverage",
        (_paper("DeepGOPlus: improved protein function prediction from sequence"),),
    ) == ()


def test_explicit_camelcase_dataset_context_remains_supported() -> None:
    assert _dataset_relation_names(
        "Evaluate on AudioSet dataset under device shift",
        (),
    ) == ("AudioSet",)
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
