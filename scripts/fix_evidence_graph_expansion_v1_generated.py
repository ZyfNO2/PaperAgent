from __future__ import annotations

from pathlib import Path


METHOD = Path("src/paperagent/method_design_draft.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")


def main() -> int:
    source = METHOD.read_text(encoding="utf-8")
    old = (
        '                        f"review source {primary.stable_identifier}; '
        'implementation baseline unresolved"\n'
    )
    new = (
        '                        (\n'
        '                            f"review source {primary.stable_identifier}; "\n'
        '                            "implementation baseline unresolved"\n'
        '                        )\n'
    )
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError("missing inferred baseline review wrapping target")
    METHOD.write_text(source, encoding="utf-8")

    test_source = ADAPTER_TEST.read_text(encoding="utf-8")
    old_title = '        _paper("A verified MIMII benchmark paper"),\n'
    new_title = '        _paper("A verified industrial evaluation paper"),\n'
    if old_title in test_source:
        test_source = test_source.replace(old_title, new_title, 1)
    elif new_title not in test_source:
        raise RuntimeError("missing focused dataset relation fixture")
    ADAPTER_TEST.write_text(test_source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
