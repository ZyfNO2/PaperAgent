from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path("evals/v0_6/holdout_manifest.json")
CASE_PATH = Path("evals/v0_6/holdout_cases.v1.jsonl")
CASE_ID_PATTERN = re.compile(r"^holdout-v1-(in-domain|ood|insufficient|adversarial)-\d{3}$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
ARXIV_PATTERN = re.compile(r"^arXiv:\d{4}\.\d{4,5}$")


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in CASE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_holdout_manifest_freezes_exact_16_case_corpus() -> None:
    manifest = _load_manifest()
    cases = _load_cases()
    raw = CASE_PATH.read_bytes()

    assert manifest["status"] == "diagnostic_only_prompt_changed"
    assert manifest["replacement_holdout_required"] is True
    assert manifest["invalidated_for_final_acceptance_by_prompt_version"] == "planning.v0.1.2"
    assert manifest["raw_cases_committed"] is True
    assert manifest["case_file"] == CASE_PATH.as_posix()
    assert manifest["expected_case_count"] == 16
    assert len(cases) == manifest["expected_case_count"]
    assert manifest["expected_case_count"] == sum(manifest["category_counts"].values())
    assert Counter(case["category"] for case in cases) == Counter(manifest["category_counts"])
    assert manifest["content_digest_algorithm"] == "sha256-exact-utf8-bytes"
    assert hashlib.sha256(raw).hexdigest() == manifest["content_digest"]


def test_every_holdout_case_has_complete_acceptance_contract() -> None:
    manifest = _load_manifest()
    cases = _load_cases()
    identifiers = [case["case_id"] for case in cases]

    assert len(set(identifiers)) == len(identifiers)

    for case in cases:
        assert CASE_ID_PATTERN.fullmatch(case["case_id"])
        assert case["version"] == manifest["version"]
        assert case["title"].strip()
        assert case["task_input"].strip()
        assert case["allowed_constraints"]
        assert case["expected_terminal"] in {"succeeded", "failed", "blocked"}

        required = case["required_evidence_properties"]
        forbidden = case["forbidden_evidence_properties"]
        assert required
        assert forbidden
        assert len(required) == len(set(required))
        assert len(forbidden) == len(set(forbidden))
        assert set(required).isdisjoint(forbidden)

        checks = case["deterministic_checks"]
        check_ids = [check["check_id"] for check in checks]
        assert len(check_ids) == len(set(check_ids))
        assert {"terminal", "budget", "identifier"} <= {check["kind"] for check in checks}
        required_targets = {
            check["target"] for check in checks if check["kind"] == "required_property"
        }
        forbidden_targets = {
            check["target"] for check in checks if check["kind"] == "forbidden_property"
        }
        assert required_targets == set(required)
        assert forbidden_targets == set(forbidden)
        assert all(check["expected"] for check in checks)

        rubric = case["human_scoring_rubric"]
        assert len(rubric) == 5
        assert sum(item["weight"] for item in rubric) == 100
        assert all(item["criterion"].strip() for item in rubric)
        assert all(item["full_credit"].strip() for item in rubric)
        assert all(item["zero_credit"].strip() for item in rubric)

        budget = case["budget"]
        assert 1 <= budget["max_calls"] <= 8
        assert 1 <= budget["max_total_tokens"] <= 16_000
        assert 1 <= budget["max_wall_seconds"] <= 180
        assert 0 < budget["max_cost_usd"] <= 2.0

        references = case["reference_evidence"]
        if case["category"] in {"in_domain", "ood"}:
            assert references
        for reference in references:
            assert reference["title"].strip()
            assert reference["claim_scope"].strip()
            assert reference["source_type"].strip()
            identifier = reference["stable_identifier"]
            identifier_type = reference["identifier_type"]
            if identifier_type == "doi":
                assert DOI_PATTERN.fullmatch(identifier)
            elif identifier_type == "arxiv":
                assert ARXIV_PATTERN.fullmatch(identifier)
            else:
                raise AssertionError(f"unsupported identifier type: {identifier_type}")


def test_holdout_anti_leakage_and_review_thresholds_are_fail_closed() -> None:
    manifest = _load_manifest()
    policy = manifest["anti_leakage_policy"]
    review = manifest["review_requirements"]
    thresholds = manifest["acceptance_thresholds"]

    assert all(policy.values())
    assert manifest["development_corpus"] != manifest["case_file"]
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["frozen_against_prompt_rule_head"])

    assert review["minimum_independent_reviewers"] >= 2
    assert review["blinded"] is True
    assert review["decision_agreement_metric"] == "cohens_kappa"
    assert review["minimum_decision_agreement"] >= 0.7
    assert review["adjudicate_all_decision_disagreements"] is True

    assert thresholds["overall_minimum_accepted_cases"] >= 14
    assert thresholds["per_category_minimum_accepted_cases"] >= 3
    assert thresholds["minimum_mean_human_score"] >= 80
    assert thresholds["minimum_individual_case_score"] >= 70
    assert thresholds["maximum_false_go_rate"] == 0
    assert thresholds["maximum_critical_safety_events"] == 0
    assert thresholds["maximum_accepted_identifier_mismatches"] == 0
    assert thresholds["maximum_critical_unsupported_claims"] == 0
    assert thresholds["maximum_noncritical_unsupported_claim_rate"] <= 0.05
    assert thresholds["maximum_citation_mismatch_rate"] <= 0.05
    assert thresholds["minimum_repair_success_rate"] >= 0.8


def test_holdout_case_ids_are_not_embedded_in_prompts_or_fixtures() -> None:
    case_ids = {case["case_id"] for case in _load_cases()}
    protected_paths = [
        *Path("src/paperagent/prompts").rglob("*.md"),
        *Path("evals/academic_tailoring").rglob("*.json"),
    ]

    for path in protected_paths:
        content = path.read_text(encoding="utf-8")
        leaked = sorted(case_id for case_id in case_ids if case_id in content)
        assert not leaked, f"holdout identifiers leaked into {path}: {leaked}"
