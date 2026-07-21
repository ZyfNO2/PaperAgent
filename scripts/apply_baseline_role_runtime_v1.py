from __future__ import annotations

from pathlib import Path

ADAPTER = Path("src/paperagent/literature/adapter.py")
METHOD = Path("src/paperagent/method_design_draft.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def main() -> int:
    replace_once(
        ADAPTER,
        "_QUOTED_TITLE = re.compile(r'[\"“](?P<title>[^\"”]{8,})[\"”]')\n",
        "_QUOTED_TITLE = re.compile(r'[\"“](?P<title>[^\"”]{8,})[\"”]')\n"
        "_BASELINE_ROLE_QUERY = re.compile(\n"
        "    r\"(?:\\\\bbaselines?\\\\b|\\\\bcomparators?\\\\b|\\\\bcomparison\\\\b|基线|对照|比较|对比)\",\n"
        "    re.IGNORECASE,\n"
        ")\n",
        "baseline role pattern",
    )
    replace_once(
        ADAPTER,
        '''    title = match.group("title").strip()
    return title or None


def _identity_tokens(value: str) -> tuple[str, ...]:
''',
        '''    title = match.group("title").strip()
    return title or None


def _query_seeks_baseline_role(query: str) -> bool:
    return bool(_BASELINE_ROLE_QUERY.search(query))


def _identity_tokens(value: str) -> tuple[str, ...]:
''',
        "baseline role helper",
    )
    replace_once(
        ADAPTER,
        '''                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else "direct_query"
                )
''',
        '''                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else (
                        "baseline_role_query"
                        if _query_seeks_baseline_role(query.query)
                        else "direct_query"
                    )
                )
''',
        "baseline role relation",
    )
    replace_once(
        ADAPTER,
        '''                        {"baseline_candidate": "inferred"}
                        if relation == "parallel_via_dataset"
                        else {}
''',
        '''                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else {}
''',
        "baseline role marker",
    )
    replace_once(
        METHOD,
        '''    relation_rank = {
        "declared_identity": 3,
        "parallel_via_dataset": 2,
    }.get(relation, 0)
''',
        '''    relation_rank = {
        "declared_identity": 4,
        "baseline_role_query": 3,
        "parallel_via_dataset": 2,
    }.get(relation, 0)
''',
        "baseline rank",
    )
    replace_once(
        METHOD,
        '''        and item.metadata.get("baseline_candidate") == "inferred"
        and item.metadata.get("relation") == "parallel_via_dataset"
''',
        '''        and item.metadata.get("baseline_candidate") == "inferred"
        and item.metadata.get("relation")
        in {"baseline_role_query", "parallel_via_dataset"}
''',
        "inferred relation eligibility",
    )
    replace_once(
        METHOD,
        '''    relation_rank = {
        "direct_query": 3,
        "parallel_via_dataset": 2,
        "declared_identity": 1,
    }.get(relation, 0)
''',
        '''    relation_rank = {
        "direct_query": 4,
        "baseline_role_query": 3,
        "parallel_via_dataset": 2,
        "declared_identity": 1,
    }.get(relation, 0)
''',
        "module rank",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
