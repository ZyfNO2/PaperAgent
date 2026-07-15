"""Contract checks for the restored Re8.1 Seed Repair fixture.

These tests do not evaluate Seed Repair quality.  They prevent accidental
changes to the case count/category distribution and pin the three typo cases
documented in the committed acceptance report.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


_FIXTURE = Path(__file__).parent / "fixtures" / "seed_repair_cases.json"


def _load():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_has_declared_frozen_case_distribution():
    payload = _load()
    cases = payload["cases"]
    assert payload["case_count"] == 20
    assert len(cases) == 20
    assert Counter(case["category"] for case in cases) == {
        "exact_title": 10,
        "typo_light": 3,
        "not_found": 2,
        "disambiguation": 3,
        "conflict": 2,
    }
    case_ids = [case["case_id"] for case in cases]
    assert len(case_ids) == len(set(case_ids))


def test_fixture_pins_acceptance_report_typo_cases():
    cases = {case["case_id"]: case for case in _load()["cases"]}
    assert cases["sr_typo_01"]["input"]["title"] == (
        "An Image is Worth 16x16 Words: Transformers for Image Recogntion at Scale"
    )
    assert cases["sr_typo_02"]["input"]["title"] == (
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understading"
    )
    assert cases["sr_typo_03"]["input"]["title"] == (
        "Deep Residual Learning for Image Recogntion"
    )


def test_not_found_cases_cannot_allow_verified():
    cases = [case for case in _load()["cases"] if case["category"] == "not_found"]
    assert len(cases) == 2
    for case in cases:
        expected = case["expected"]
        assert expected["must_not_be_verified"] is True
        assert "verified" not in expected["allowed_existence_status"]


def test_fixture_records_missing_dependency_provenance():
    provenance = _load()["provenance"]
    assert provenance["status"] == "reconstructed_missing_dependency"
    assert provenance["test_contract"].endswith("TestRe81WP2Acceptance")
    assert provenance["acceptance_report"].endswith("acceptance_report.json")
