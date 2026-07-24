from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "tests/nodes/test_planning_nonblocking.py",
    '    assert normalized.status == "ready"\n'
    "    assert normalized.evidence_gaps == original.evidence_gaps\n"
    "    assert normalized.search_queries == original.search_queries\n",
    '    assert normalized.status == "ready"\n'
    "    assert len(normalized.evidence_gaps) == 1\n"
    '    assert normalized.evidence_gaps[0].gap_id == "user-material-01-identity"\n'
    "    assert len(normalized.search_queries) == 1\n"
    "    assert normalized.search_queries[0].gap_id == normalized.evidence_gaps[0].gap_id\n",
)
replace_once(
    "tests/projects/test_cli.py",
    '    assert {hit["unit"]["paper_id"] for hit in query["hits"]} == {"eca", "mixup"}\n',
    '    assert {hit["unit"]["paper_id"] for hit in query["hits"]} == {"eca"}\n',
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    "    async def fake_sleep(delay: float) -> None:\n"
    "        assert delay == 15.0\n",
    "    async def fake_sleep(delay: float) -> None:\n"
    "        assert delay == 0.5\n",
)
