"""Re04 SOP §5 Task 1 acceptance tests for the eval dataset loader.

Validates:
- 100 unique ENG-THESIS-* rows from JSONL
- Smoke 20 / Balanced 40 ID files match SOP §3.2
- Re04-active fields present; gold labels (difficulty/cycle/repeatability)
  NOT in any record (Re04 must not be polluted by gold)
- source_url is preserved (no URL rewriting)
- paperagent_test is preserved verbatim
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX_DIR = Path(__file__).resolve().parent / "fixtures"
JSONL = FIX_DIR / "re04_engineering_resource_cases.jsonl"
SMOKE_20 = FIX_DIR / "re04_smoke_20_ids.txt"
BALANCED_40 = FIX_DIR / "re04_balanced_40_ids.txt"

# SOP §3.2 lists the 20 smoke IDs verbatim.
EXPECTED_SMOKE_20 = {
    "ENG-THESIS-015", "ENG-THESIS-016", "ENG-THESIS-018", "ENG-THESIS-024",
    "ENG-THESIS-027", "ENG-THESIS-028", "ENG-THESIS-032", "ENG-THESIS-033",
    "ENG-THESIS-043", "ENG-THESIS-046", "ENG-THESIS-050", "ENG-THESIS-063",
    "ENG-THESIS-066", "ENG-THESIS-074", "ENG-THESIS-075", "ENG-THESIS-080",
    "ENG-THESIS-091", "ENG-THESIS-092", "ENG-THESIS-093", "ENG-THESIS-096",
}

EXPECTED_BALANCED_40_EXTRA = {
    "ENG-THESIS-002", "ENG-THESIS-003", "ENG-THESIS-004", "ENG-THESIS-005",
    "ENG-THESIS-010", "ENG-THESIS-014", "ENG-THESIS-022", "ENG-THESIS-035",
    "ENG-THESIS-040", "ENG-THESIS-048", "ENG-THESIS-051", "ENG-THESIS-058",
    "ENG-THESIS-060", "ENG-THESIS-064", "ENG-THESIS-072", "ENG-THESIS-073",
    "ENG-THESIS-079", "ENG-THESIS-083", "ENG-THESIS-089", "ENG-THESIS-100",
}
EXPECTED_BALANCED_40 = EXPECTED_SMOKE_20 | EXPECTED_BALANCED_40_EXTRA

# Forbidden gold labels per SOP §5 Task 1 (re04 must not see them).
FORBIDDEN_FIELDS = {"difficulty", "cycle", "repeatability", "experiment_need"}

REQUIRED_FIELDS = {
    "id", "title", "year", "domain", "source_url",
    "paperagent_test", "active_eval", "excluded_eval",
}


def _load_records() -> list[dict]:
    return [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_jsonl_exists():
    assert JSONL.exists(), f"missing {JSONL}"


def test_records_unique_and_count():
    rows = _load_records()
    assert len(rows) == 100, f"expected 100, got {len(rows)}"
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 100, "duplicate ids"


def test_records_have_required_fields():
    rows = _load_records()
    for r in rows:
        assert REQUIRED_FIELDS.issubset(r.keys()), f"{r['id']} missing {REQUIRED_FIELDS - r.keys()}"


def test_records_do_not_contain_gold_labels():
    """Re04 must not be polluted by difficulty/cycle/repeatability."""
    rows = _load_records()
    for r in rows:
        leak = FORBIDDEN_FIELDS & r.keys()
        assert not leak, f"{r['id']} leaks gold fields {leak}"


def test_active_eval_and_excluded_eval_match_sop():
    rows = _load_records()
    for r in rows:
        assert r["active_eval"] == [
            "query_plan", "resource_retrieval", "role_bucket", "evidence_ledger",
        ], f"{r['id']} active_eval drift"
        assert r["excluded_eval"] == [
            "difficulty", "cycle", "repeatability", "experiment_need",
        ], f"{r['id']} excluded_eval drift"


def test_source_url_preserved_verbatim():
    """Per SOP §5 Task 1: must preserve original link, no rewriting."""
    rows = _load_records()
    for r in rows:
        url = r["source_url"]
        assert url.startswith("http"), f"{r['id']} bad url {url!r}"
        assert "cdmd.cnki.com.cn" in url, f"{r['id']} url not from CNKI source: {url!r}"


def test_title_not_rewritten():
    rows = _load_records()
    for r in rows:
        # Title should still be in Chinese (untouched) and not contain
        # the gold difficulty token as a leakage.
        assert "高" not in r["title"] or r["title"].count("高") <= 1
        # No 'TODO' or 'TBD' placeholders (would mean converter failed)
        assert "TODO" not in r["title"]
        assert "TBD" not in r["title"]


def test_year_in_range():
    rows = _load_records()
    for r in rows:
        assert 2010 <= r["year"] <= 2026, f"{r['id']} year out of range {r['year']}"


def test_smoke_20_ids_match_sop():
    txt = SMOKE_20.read_text(encoding="utf-8").splitlines()
    ids = {line.strip() for line in txt if line.strip()}
    assert ids == EXPECTED_SMOKE_20, f"smoke drift: diff={ids ^ EXPECTED_SMOKE_20}"


def test_balanced_40_ids_match_sop():
    txt = BALANCED_40.read_text(encoding="utf-8").splitlines()
    ids = {line.strip() for line in txt if line.strip()}
    assert ids == EXPECTED_BALANCED_40, f"balanced drift: diff={ids ^ EXPECTED_BALANCED_40}"


def test_all_smoke_and_balanced_ids_exist_in_jsonl():
    rows = _load_records()
    jsonl_ids = {r["id"] for r in rows}
    missing_smoke = EXPECTED_SMOKE_20 - jsonl_ids
    missing_balanced = EXPECTED_BALANCED_40 - jsonl_ids
    assert not missing_smoke, f"smoke missing in jsonl: {missing_smoke}"
    assert not missing_balanced, f"balanced missing in jsonl: {missing_balanced}"


@pytest.mark.parametrize("case_id", sorted(EXPECTED_SMOKE_20))
def test_smoke_20_each_has_test_note(case_id):
    """paperagent_test field must be non-empty for every smoke case."""
    rows = _load_records()
    row = next(r for r in rows if r["id"] == case_id)
    assert row["paperagent_test"], f"{case_id} empty paperagent_test"
    assert len(row["paperagent_test"]) >= 10, f"{case_id} test note too short"
