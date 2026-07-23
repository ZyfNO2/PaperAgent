from __future__ import annotations

from pathlib import Path

METHOD_DESIGN = Path("src/paperagent/method_design_draft.py")
METHOD_EVIDENCE = Path("src/paperagent/method_evidence.py")
METHOD_TESTS = Path("tests/methodology/test_method_design_draft.py")
TRIGGER = Path(".github/evidence-bound-module-v2-run.txt")


def replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_method_evidence_metadata() -> None:
    replace_once(
        METHOD_EVIDENCE,
        '        "environment_fingerprint",\n',
        '''        "environment_fingerprint",
        "relation",
        "module_candidate",
        "relevance_score",
        "rank_score",
        "module_aliases",
''',
        label="method evidence module metadata allowlist",
    )


def patch_declared_module_aliases() -> None:
    marker = '''def _module_candidate_marker(item: EvidenceItem) -> bool:
    return item.metadata.get("module_candidate", "").casefold() in {
        "true",
        "1",
        "yes",
        "declared",
        "inferred",
    }
'''
    helper = marker + '''


def _module_titles_and_aliases(item: EvidenceItem) -> tuple[str, ...]:
    aliases = tuple(
        part.strip(" []\\\"'")
        for part in re.split(r"[|,;]", item.metadata.get("module_aliases", ""))
        if part.strip(" []\\\"'")
    )
    return (item.title, *aliases)
'''
    replace_once(
        METHOD_DESIGN,
        marker,
        helper,
        label="module title alias helper",
    )
    replace_once(
        METHOD_DESIGN,
        '''        if declared_titles and not any(
            _titles_equivalent(item.title, title) for title in declared_titles
        ):
            continue
''',
        '''        if declared_titles and not any(
            _titles_equivalent(candidate_title, declared_title)
            for candidate_title in _module_titles_and_aliases(item)
            for declared_title in declared_titles
        ):
            continue
''',
        label="declared module alias selection",
    )


def patch_tests() -> None:
    replace_once(
        METHOD_TESTS,
        "from paperagent.method_evidence import bind_method_evidence\n",
        "from paperagent.method_evidence import accepted_evidence_ledger, bind_method_evidence\n",
        label="method evidence ledger test import",
    )
    tests = '''


def test_declared_module_alias_matches_module_metadata() -> None:
    state = _state()
    request = state["request"]
    evidence = state["evidence"]
    assert request is not None
    assert evidence is not None
    module_item = evidence.items[1].model_copy(
        update={
            "metadata": {
                **evidence.items[1].metadata,
                "module_aliases": "SFF|ShallowFusion",
            }
        }
    )
    alias_state = cast(
        PaperAgentState,
        {
            **state,
            "request": request.model_copy(
                update={
                    "user_material_refs": ["SFF [declared role: parallel paper]"]
                }
            ),
            "evidence": evidence.model_copy(
                update={"items": [evidence.items[0], module_item]}
            ),
        },
    )

    proposal = build_method_proposal(alias_state, _draft())

    assert proposal.methodology_plan.modules[0].evidence_id == _MODULE_EVIDENCE_ID


def test_method_evidence_payload_preserves_safe_module_metadata() -> None:
    evidence = _state()["evidence"]
    assert evidence is not None
    module_item = evidence.items[1].model_copy(
        update={
            "metadata": {
                **evidence.items[1].metadata,
                "module_aliases": "SFF|ShallowFusion",
            }
        }
    )
    bundle = evidence.model_copy(
        update={"items": [evidence.items[0], module_item]}
    )

    payload = accepted_evidence_ledger(bundle)
    module_payload = next(
        item for item in payload if item["evidence_id"] == _MODULE_EVIDENCE_ID
    )

    assert module_payload["metadata"]["relation"] == "module_role_query"
    assert module_payload["metadata"]["module_candidate"] == "inferred"
    assert module_payload["metadata"]["relevance_score"] == "0.92"
    assert module_payload["metadata"]["module_aliases"] == "SFF|ShallowFusion"
'''
    text = METHOD_TESTS.read_text(encoding="utf-8")
    marker = "def test_declared_module_alias_matches_module_metadata"
    if marker not in text:
        METHOD_TESTS.write_text(text.rstrip() + tests + "\n", encoding="utf-8")


def main() -> None:
    patch_method_evidence_metadata()
    patch_declared_module_aliases()
    patch_tests()
    TRIGGER.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
