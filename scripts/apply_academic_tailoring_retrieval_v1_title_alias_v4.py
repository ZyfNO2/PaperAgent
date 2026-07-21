from __future__ import annotations

from pathlib import Path


SCORER_PATH = Path("scripts/score_academic_tailoring_retrieval_v1.py")
METHOD_PATH = Path("src/paperagent/method_design_draft.py")


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    if old in source:
        return source.replace(old, new, 1)
    if new in source:
        return source
    raise RuntimeError(f"{label} block not found")


def _patch_scorer() -> None:
    source = SCORER_PATH.read_text(encoding="utf-8")
    old = '''def _titles_related(left: str, right: str) -> bool:
    left_tokens = set(_normalize(left).split())
    right_tokens = set(_normalize(right).split())
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    length_ratio = min(len(left_tokens), len(right_tokens)) / max(
        len(left_tokens), len(right_tokens)
    )
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75
'''
    new = '''def _is_exact_acronym_alias(alias: str, full_title: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", alias)
    full_tokens = _normalize(full_title).split()
    return (
        len(compact) >= 3
        and compact.isupper()
        and bool(full_tokens)
        and compact.casefold() == full_tokens[0]
    )


def _titles_related(left: str, right: str) -> bool:
    left_tokens = set(_normalize(left).split())
    right_tokens = set(_normalize(right).split())
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if _is_exact_acronym_alias(left, right) or _is_exact_acronym_alias(right, left):
        return True
    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    length_ratio = min(len(left_tokens), len(right_tokens)) / max(
        len(left_tokens), len(right_tokens)
    )
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75
'''
    source = _replace_once(source, old, new, label="scorer title matcher")
    SCORER_PATH.write_text(source, encoding="utf-8")


def _patch_method_design() -> None:
    source = METHOD_PATH.read_text(encoding="utf-8")
    old = '''def _titles_equivalent(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    union = left_set | right_set
    overlap = left_set & right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75
'''
    new = '''def _is_exact_acronym_alias(alias: str, full_title: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", alias)
    full_tokens = _title_tokens(full_title)
    return (
        len(compact) >= 3
        and compact.isupper()
        and bool(full_tokens)
        and compact.casefold() == full_tokens[0]
    )


def _titles_equivalent(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if _is_exact_acronym_alias(left, right) or _is_exact_acronym_alias(right, left):
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    union = left_set | right_set
    overlap = left_set & right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75
'''
    source = _replace_once(source, old, new, label="method title matcher")
    METHOD_PATH.write_text(source, encoding="utf-8")


def main() -> int:
    _patch_scorer()
    _patch_method_design()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
