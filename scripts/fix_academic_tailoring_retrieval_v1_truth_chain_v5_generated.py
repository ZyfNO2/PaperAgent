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


def main() -> int:
    replace_once(
        SCORER,
        '    identity_text = _normalize("\n".join(_identity_values(item)))\n',
        '    identity_text = _normalize("\\n".join(_identity_values(item)))\n',
        "identity newline escape",
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
        '            "PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition [declared role: baseline]"\n',
        '            "PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern "\n'
        '            "Recognition [declared role: baseline]"\n',
        "method test title wrapping",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
