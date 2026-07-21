from __future__ import annotations

from pathlib import Path


PATCH_SCRIPT = Path("scripts/apply_academic_tailoring_retrieval_v1_truth_chain_v5.py")


def main() -> int:
    source = PATCH_SCRIPT.read_text(encoding="utf-8")
    old = '''    if new in source:
        return source
    raise RuntimeError(f"missing replacement marker: {label}")
'''
    new = '''    if new in source:
        return source
    if label == "dataset evidence quality":
        start = source.find("def _accepted_asset_matches(")
        end = source.find("\\n\\ndef _declared_baseline_titles", start)
        if start >= 0 and end > start:
            return source[:start] + new.rstrip() + source[end:]
    raise RuntimeError(f"missing replacement marker: {label}")
'''
    if old in source:
        source = source.replace(old, new, 1)
    elif 'label == "dataset evidence quality"' not in source:
        raise RuntimeError("replace_once helper marker not found")
    PATCH_SCRIPT.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
