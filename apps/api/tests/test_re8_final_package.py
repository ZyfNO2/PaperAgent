"""Tests for Re8.0 Task 7 — Final Research Package assembly (P1-3).

Covers ``_assemble_final_research_package`` in
``apps.api.app.services.agents.graph.nodes.content``. The function is PURE
(no I/O, no side effects): it takes a state dict and returns a package dict
with the 7 sections required by spec §"Final Research Package":

  1. seed_audit_summary   — key fields from each SeedPaperCard
  2. tailor_summary       — key fields from tailored_method + contribution_type
  3. gate_results         — LAST verdict of each of the 3 Reflection Gates
  4. ledger_entries       — key fields from each ReasoningLedgerEntry
  5. evidence_gap_status  — counts by status + list of open gap summaries
  6. falsifiable_hypothesis — hypothesis string (or "unspecified")
  7. fused_verdict        — verdict + rationale from _compute_fused_verdict

Spec scenario: "Package assembled — WHEN pipeline completes THEN
final_research_package contains all 7 sections with non-empty values."
"""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from apps.api.app.services.agents.graph.nodes.content import (
    _assemble_final_research_package,
    _compute_fused_verdict,
)
from apps.api.app.services.agents.graph.nodes.reflection_gates import (
    GATE_FINAL_REVIEW,
    GATE_SEED_AUDIT,
    GATE_TAILOR,
)


# ── State builders ─────────────────────────────────────────────────────────


def _gate_entry(verdict: str, round_idx: int = 0, **extra: Any) -> dict[str, Any]:
    """Build a single reflection_gate_results entry."""
    entry: dict[str, Any] = {
        "gate_name": "test_gate",
        "verdict": verdict,
        "round_idx": round_idx,
        "re_search_requests": [],
        "unresolved_gaps": [],
        "rationale": "",
        "generated_by": "llm",
    }
    entry.update(extra)
    return entry


def _seed_card(
    *,
    seed_id: str = "S1",
    resolved_title: str = "Paper Title",
    existence_status: str = "verified",
    role: str = "classic_anchor",
    fulltext_status: str = "fulltext_parsed",
) -> dict[str, Any]:
    return {
        "seed_id": seed_id,
        "input_form": "doi",
        "resolved_title": resolved_title,
        "authors": ["Author A"],
        "year": 2023,
        "doi": "10.1234/test",
        "existence_status": existence_status,
        "fulltext_status": fulltext_status,
        "role": role,
    }


def _full_state() -> dict[str, Any]:
    """A well-formed state with every section populated.

    Used as the base for positive and negative tests. Every field that
    `_assemble_final_research_package` reads is set to a non-empty value
    so the assembled package's 7 sections are all non-empty.
    """
    return {
        # 1. seed_cards
        "seed_cards": [
            _seed_card(seed_id="S1", resolved_title="YOLO for Steel Defect",
                       existence_status="verified", role="classic_anchor",
                       fulltext_status="fulltext_parsed"),
            _seed_card(seed_id="S2", resolved_title="XLM-R Reproduction",
                       existence_status="ambiguous", role="unknown",
                       fulltext_status="metadata_only"),
        ],
        # 2. tailored_method (production schema from tailor_skill_adapter)
        "tailored_method": {
            "primary_baseline": {
                "baseline_id": "B1",
                "title": "YOLOv5 Baseline",
                "selection_reason": "SOTA on steel defect",
            },
            "candidate_modules": [
                {"module_id": "M1", "name": "Attention Block"},
            ],
            "assembly_plan": {
                "description": "Inject attention block into YOLOv5 neck",
                "steps": ["step1", "step2"],
                "expected_interfaces": ["neck"],
            },
            "ablation_matrix": [
                {"experiment_id": "baseline"},
                {"experiment_id": "A"},
                {"experiment_id": "B"},
                {"experiment_id": "A+B"},
            ],
            "verdict": "GO",
            "verdict_reason": "all checks pass",
            "generated_by": "llm",
        },
        "contribution_type": "methodological",
        # 3. reflection_gate_results — multi-round for seed_audit to test
        # last-entry-wins semantics.
        "reflection_gate_results": {
            GATE_SEED_AUDIT: [
                _gate_entry("revise", round_idx=0, rationale="round0"),
                _gate_entry("pass", round_idx=1, rationale="round1 passed"),
            ],
            GATE_TAILOR: [
                _gate_entry("pass", round_idx=0,
                            rationale="ablation ok",
                            re_search_requests=[]),
            ],
            GATE_FINAL_REVIEW: [
                _gate_entry("pass", round_idx=0,
                            rationale="narrative within evidence",
                            re_search_requests=["search_method_family"]),
            ],
        },
        # 4. reasoning_ledger
        "reasoning_ledger": [
            {
                "decision_id": "D1",
                "stage": "seed_audit",
                "decision": "verified S1",
                "evidence_ids": [],
                "alternatives_considered": [],
                "rejection_reasons": [],
                "hypothesis": None,
                "falsifier": None,
                "next_action": "continue",
                "confidence": 0.9,
                "status": "verified",
            },
            {
                "decision_id": "D2",
                "stage": "tailor",
                "decision": "GO",
                "evidence_ids": [],
                "alternatives_considered": [],
                "rejection_reasons": [],
                "hypothesis": None,
                "falsifier": None,
                "next_action": "issue GO",
                "confidence": 0.8,
                "status": "evidence_backed",
            },
        ],
        # 5. evidence_gaps — mix of statuses and types. Note: NO critical-
        # type gap (current_baseline/competing_method/dataset/mechanism) is
        # left 'open', otherwise rule 6 of _compute_fused_verdict would cap
        # the fused verdict at CONDITIONAL and the GO-path tests below
        # would fail. Critical-type gaps here are satisfied / partially_
        # satisfied; open gaps are all non-critical types (repo /
        # counter_evidence) so they appear in open_gaps without blocking GO.
        "evidence_gaps": [
            {"gap_id": "G1", "gap_type": "current_baseline", "status": "satisfied",
             "question": "Identify SOTA baseline"},
            {"gap_id": "G2", "gap_type": "dataset", "status": "satisfied",
             "question": "Need steel defect dataset"},
            {"gap_id": "G3", "gap_type": "repo", "status": "open",
             "question": "Need reproduction repo"},
            {"gap_id": "G4", "gap_type": "mechanism", "status": "partially_satisfied",
             "question": "Mechanism of attention"},
            {"gap_id": "G5", "gap_type": "environment", "status": "blocked",
             "question": "GPU environment"},
            {"gap_id": "G6", "gap_type": "counter_evidence", "status": "open",
             "question": "Need counter-evidence paper"},
        ],
        # 6. falsifiable_hypothesis
        "falsifiable_hypothesis": "Attention block on YOLOv5 neck improves mAP by >=2 points on steel defect dataset.",
        # 7. fused_verdict inputs — make it GO so the section is non-empty.
        "novelty_review_verdict": "accepted",
    }


# ── Section structure ──────────────────────────────────────────────────────


EXPECTED_SECTIONS = (
    "seed_audit_summary",
    "tailor_summary",
    "gate_results",
    "ledger_entries",
    "evidence_gap_status",
    "falsifiable_hypothesis",
    "fused_verdict",
)


class TestPackageStructure:
    def test_well_formed_state_has_7_non_empty_sections(self):
        """Spec scenario: 'Package assembled' — well-formed state produces
        a package with all 7 sections present AND non-empty."""
        pkg = _assemble_final_research_package(_full_state())
        # All 7 sections present (exact key set).
        assert set(pkg.keys()) == set(EXPECTED_SECTIONS)
        # Each section non-empty.
        assert len(pkg["seed_audit_summary"]) == 2
        assert pkg["tailor_summary"]["verdict"] == "GO"
        assert pkg["tailor_summary"]["ablation_matrix_count"] == 4
        assert len(pkg["gate_results"]) == 3
        assert len(pkg["ledger_entries"]) == 2
        assert pkg["evidence_gap_status"]["counts"]["open"] == 2
        assert pkg["falsifiable_hypothesis"].startswith("Attention block")
        assert pkg["fused_verdict"]["verdict"] == "GO"

    def test_empty_state_still_has_7_sections(self):
        """Empty state (no seeds, no gates, no ledger) must not crash —
        every section degrades to an empty/default value."""
        pkg = _assemble_final_research_package({})
        # All 7 sections present.
        assert set(pkg.keys()) == set(EXPECTED_SECTIONS)
        # Defaults.
        assert pkg["seed_audit_summary"] == []
        assert pkg["tailor_summary"] == {
            "verdict": "",
            "core_method": "",
            "baseline_model": "",
            "ablation_matrix_count": 0,
            "contribution_type": "unknown",
        }
        # gate_results: 3 keys, each with empty default fields.
        assert set(pkg["gate_results"].keys()) == {
            GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW,
        }
        for gate_name in (GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW):
            entry = pkg["gate_results"][gate_name]
            assert entry == {
                "verdict": "", "round_idx": 0,
                "rationale": "", "re_search_requests": [],
            }
        assert pkg["ledger_entries"] == []
        assert pkg["evidence_gap_status"] == {
            "counts": {"open": 0, "satisfied": 0,
                       "partially_satisfied": 0, "blocked": 0},
            "open_gaps": [],
        }
        assert pkg["falsifiable_hypothesis"] == "unspecified"
        # Empty state → fused_verdict default (CONDITIONAL per rule 8).
        assert pkg["fused_verdict"]["verdict"] == "CONDITIONAL"
        assert pkg["fused_verdict"]["rationale"] == "insufficient signals for GO"

    def test_function_is_pure_no_state_mutation(self):
        """_assemble_final_research_package must not mutate its input."""
        state = _full_state()
        snapshot = copy.deepcopy(state)
        _assemble_final_research_package(state)
        _assemble_final_research_package(state)
        assert state == snapshot


# ── Section 1: seed_audit_summary ──────────────────────────────────────────


class TestSeedAuditSummary:
    def test_extracts_exact_key_fields(self):
        """seed_audit_summary entries must contain exactly the 5 key fields
        (seed_id, resolved_title, existence_status, role, fulltext_status)
        — no extra fields, no missing fields."""
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        for entry in pkg["seed_audit_summary"]:
            assert set(entry.keys()) == {
                "seed_id", "resolved_title", "existence_status",
                "role", "fulltext_status",
            }

    def test_extracts_correct_values(self):
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        s1 = pkg["seed_audit_summary"][0]
        assert s1["seed_id"] == "S1"
        assert s1["resolved_title"] == "YOLO for Steel Defect"
        assert s1["existence_status"] == "verified"
        assert s1["role"] == "classic_anchor"
        assert s1["fulltext_status"] == "fulltext_parsed"
        s2 = pkg["seed_audit_summary"][1]
        assert s2["seed_id"] == "S2"
        assert s2["existence_status"] == "ambiguous"
        assert s2["role"] == "unknown"
        assert s2["fulltext_status"] == "metadata_only"

    def test_missing_fields_get_defaults(self):
        """A seed card with missing existence_status / role / fulltext_status
        gets the documented defaults (ambiguous / unknown / metadata_only)."""
        pkg = _assemble_final_research_package({
            "seed_cards": [{"seed_id": "Sx"}],  # all other fields missing
        })
        assert pkg["seed_audit_summary"] == [{
            "seed_id": "Sx",
            "resolved_title": "",
            "existence_status": "ambiguous",
            "role": "unknown",
            "fulltext_status": "metadata_only",
        }]

    def test_non_dict_seed_card_skipped(self):
        """Non-dict entries in seed_cards must be silently skipped."""
        pkg = _assemble_final_research_package({
            "seed_cards": ["not a dict", None, 42, {"seed_id": "Sok"}],
        })
        assert len(pkg["seed_audit_summary"]) == 1
        assert pkg["seed_audit_summary"][0]["seed_id"] == "Sok"


# ── Section 2: tailor_summary ──────────────────────────────────────────────


class TestTailorSummary:
    def test_summary_has_5_key_fields(self):
        pkg = _assemble_final_research_package(_full_state())
        assert set(pkg["tailor_summary"].keys()) == {
            "verdict", "core_method", "baseline_model",
            "ablation_matrix_count", "contribution_type",
        }

    def test_summary_extracts_correct_values(self):
        pkg = _assemble_final_research_package(_full_state())
        ts = pkg["tailor_summary"]
        assert ts["verdict"] == "GO"
        assert ts["core_method"] == "Inject attention block into YOLOv5 neck"
        assert ts["baseline_model"] == "YOLOv5 Baseline"
        assert ts["ablation_matrix_count"] == 4
        assert ts["contribution_type"] == "methodological"

    def test_explicit_core_method_field_wins_over_assembly_description(self):
        """If tailored_method carries an explicit 'core_method' field (test
        fixtures / future schema), it takes precedence over
        assembly_plan.description."""
        pkg = _assemble_final_research_package({
            "tailored_method": {
                "verdict": "GO",
                "core_method": "explicit-method-name",
                "assembly_plan": {"description": "should-not-win"},
                "primary_baseline": {"title": "B"},
                "ablation_matrix": [],
            },
        })
        assert pkg["tailor_summary"]["core_method"] == "explicit-method-name"

    def test_missing_tailored_method_yields_empty_defaults(self):
        pkg = _assemble_final_research_package({})
        ts = pkg["tailor_summary"]
        assert ts == {
            "verdict": "",
            "core_method": "",
            "baseline_model": "",
            "ablation_matrix_count": 0,
            "contribution_type": "unknown",
        }


# ── Section 3: gate_results ────────────────────────────────────────────────


class TestGateResults:
    def test_takes_last_entry_not_first(self):
        """Spec: gate_results maps each gate name to its LAST verdict. With
        multiple rounds, the LAST entry's verdict/round_idx must win."""
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        # seed_audit_gate had [revise@0, pass@1] — last wins.
        sa = pkg["gate_results"][GATE_SEED_AUDIT]
        assert sa["verdict"] == "pass"
        assert sa["round_idx"] == 1
        assert sa["rationale"] == "round1 passed"

    def test_each_gate_has_4_fields(self):
        pkg = _assemble_final_research_package(_full_state())
        for gate_name in (GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW):
            entry = pkg["gate_results"][gate_name]
            assert set(entry.keys()) == {
                "verdict", "round_idx", "rationale", "re_search_requests",
            }

    def test_re_search_requests_passed_through(self):
        """re_search_requests from the last entry must be carried as a
        list of strings."""
        pkg = _assemble_final_research_package(_full_state())
        fr = pkg["gate_results"][GATE_FINAL_REVIEW]
        assert fr["re_search_requests"] == ["search_method_family"]

    def test_missing_gate_yields_empty_default(self):
        """A gate with no entries (Lite Chain short-circuit / never run)
        yields an empty default, not a missing key."""
        pkg = _assemble_final_research_package({
            "reflection_gate_results": {GATE_SEED_AUDIT: [_gate_entry("pass")]},
        })
        # All 3 gate keys always present.
        assert set(pkg["gate_results"].keys()) == {
            GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW,
        }
        assert pkg["gate_results"][GATE_SEED_AUDIT]["verdict"] == "pass"
        # The two missing gates get empty defaults.
        for missing_gate in (GATE_TAILOR, GATE_FINAL_REVIEW):
            assert pkg["gate_results"][missing_gate] == {
                "verdict": "", "round_idx": 0,
                "rationale": "", "re_search_requests": [],
            }

    def test_malformed_round_idx_falls_back_to_zero(self):
        """A non-int round_idx (string / None) must fall back to 0, not crash."""
        pkg = _assemble_final_research_package({
            "reflection_gate_results": {
                GATE_SEED_AUDIT: [{"verdict": "pass", "round_idx": "two"}],
            },
        })
        assert pkg["gate_results"][GATE_SEED_AUDIT]["round_idx"] == 0


# ── Section 4: ledger_entries ──────────────────────────────────────────────


class TestLedgerEntries:
    def test_each_entry_has_5_fields(self):
        pkg = _assemble_final_research_package(_full_state())
        for entry in pkg["ledger_entries"]:
            assert set(entry.keys()) == {
                "decision_id", "stage", "decision", "status", "confidence",
            }

    def test_extracts_correct_values(self):
        pkg = _assemble_final_research_package(_full_state())
        d1 = pkg["ledger_entries"][0]
        assert d1["decision_id"] == "D1"
        assert d1["stage"] == "seed_audit"
        assert d1["decision"] == "verified S1"
        assert d1["status"] == "verified"
        assert d1["confidence"] == pytest.approx(0.9)

    def test_malformed_confidence_falls_back_to_zero(self):
        """A non-numeric confidence must fall back to 0.0, not crash."""
        pkg = _assemble_final_research_package({
            "reasoning_ledger": [
                {"decision_id": "Dx", "stage": "tailor",
                 "decision": "x", "status": "proposed",
                 "confidence": "not-a-number"},
            ],
        })
        assert pkg["ledger_entries"][0]["confidence"] == 0.0

    def test_missing_status_defaults_to_proposed(self):
        pkg = _assemble_final_research_package({
            "reasoning_ledger": [{"decision_id": "Dx", "stage": "tailor",
                                  "decision": "x"}],
        })
        assert pkg["ledger_entries"][0]["status"] == "proposed"


# ── Section 5: evidence_gap_status ─────────────────────────────────────────


class TestEvidenceGapStatus:
    def test_counts_by_status_correct(self):
        """Spec: evidence_gap_status has counts by status
        (open/satisfied/partially_satisfied/blocked)."""
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        counts = pkg["evidence_gap_status"]["counts"]
        # full_state has: 2 satisfied (G1,G2), 2 open (G3,G6),
        # 1 partially_satisfied (G4), 1 blocked (G5).
        assert counts == {
            "open": 2,
            "satisfied": 2,
            "partially_satisfied": 1,
            "blocked": 1,
        }

    def test_counts_always_have_4_buckets(self):
        """Even with empty state, all 4 status buckets must be present
        with count 0 — never missing."""
        pkg = _assemble_final_research_package({})
        assert set(pkg["evidence_gap_status"]["counts"].keys()) == {
            "open", "satisfied", "partially_satisfied", "blocked",
        }
        assert all(
            v == 0 for v in pkg["evidence_gap_status"]["counts"].values()
        )

    def test_open_gaps_listed_with_summary_fields(self):
        """Each open gap must appear in open_gaps with gap_id/question/gap_type."""
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        open_gaps = pkg["evidence_gap_status"]["open_gaps"]
        # full_state has 2 open gaps (G3 repo, G6 counter_evidence) — both
        # non-critical types so they don't block the GO fused verdict.
        assert len(open_gaps) == 2
        ids = {g["gap_id"] for g in open_gaps}
        assert ids == {"G3", "G6"}
        for g in open_gaps:
            assert set(g.keys()) == {"gap_id", "question", "gap_type"}

    def test_unknown_status_bucketed_under_open(self):
        """An unknown status string must not crash — it falls under 'open'
        conservatively so the total still adds up."""
        pkg = _assemble_final_research_package({
            "evidence_gaps": [
                {"gap_id": "Gx", "gap_type": "existence",
                 "status": "weird_status", "question": "?"},
            ],
        })
        assert pkg["evidence_gap_status"]["counts"]["open"] == 1
        # Unknown status does NOT appear in open_gaps list (only status='open'
        # gaps do), but it IS counted under the 'open' bucket.
        assert pkg["evidence_gap_status"]["open_gaps"] == []


# ── Section 6: falsifiable_hypothesis ──────────────────────────────────────


class TestFalsifiableHypothesis:
    def test_present_hypothesis_passed_through(self):
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        assert pkg["falsifiable_hypothesis"] == (
            state["falsifiable_hypothesis"]
        )

    def test_missing_hypothesis_is_unspecified(self):
        pkg = _assemble_final_research_package({})
        assert pkg["falsifiable_hypothesis"] == "unspecified"

    def test_empty_string_hypothesis_is_unspecified(self):
        pkg = _assemble_final_research_package({
            "falsifiable_hypothesis": "   ",
        })
        assert pkg["falsifiable_hypothesis"] == "unspecified"

    def test_non_string_hypothesis_is_unspecified(self):
        """A non-string hypothesis (None / int / dict) must not crash —
        treated as 'unspecified'."""
        for bad in (None, 42, {"h": "x"}, ["a"]):
            pkg = _assemble_final_research_package({
                "falsifiable_hypothesis": bad,
            })
            assert pkg["falsifiable_hypothesis"] == "unspecified"


# ── Section 7: fused_verdict ───────────────────────────────────────────────


class TestFusedVerdictSection:
    def test_section_matches_compute_fused_verdict_output(self):
        """The fused_verdict section must exactly mirror what
        _compute_fused_verdict returns for the same state."""
        state = _full_state()
        pkg = _assemble_final_research_package(state)
        expected_verdict, expected_rationale = _compute_fused_verdict(state)
        assert pkg["fused_verdict"] == {
            "verdict": expected_verdict,
            "rationale": expected_rationale,
        }

    def test_section_has_verdict_and_rationale_keys(self):
        pkg = _assemble_final_research_package(_full_state())
        assert set(pkg["fused_verdict"].keys()) == {"verdict", "rationale"}

    def test_full_state_is_go(self):
        """Sanity: the full_state fixture produces fused_verdict=GO."""
        pkg = _assemble_final_research_package(_full_state())
        assert pkg["fused_verdict"]["verdict"] == "GO"
        assert pkg["fused_verdict"]["rationale"] == "all checks passed"

    def test_blocked_state_propagates(self):
        """If seed_audit_gate is unresolved, the package's fused_verdict
        section must reflect BLOCKED."""
        state = _full_state()
        state["reflection_gate_results"][GATE_SEED_AUDIT] = [
            _gate_entry("unresolved"),
        ]
        pkg = _assemble_final_research_package(state)
        assert pkg["fused_verdict"]["verdict"] == "BLOCKED"


# ── JSON serializability ───────────────────────────────────────────────────


class TestJsonSerializable:
    def test_full_state_package_is_json_serializable(self):
        """The package must be serializable to JSON (no datetime / bytes /
        set / custom objects). Spec: 'All values must be JSON-serializable'."""
        pkg = _assemble_final_research_package(_full_state())
        # json.dumps raises TypeError on non-serializable values.
        serialized = json.dumps(pkg, ensure_ascii=False)
        # Round-trip: parse back and compare structurally.
        assert json.loads(serialized) == pkg

    def test_empty_state_package_is_json_serializable(self):
        pkg = _assemble_final_research_package({})
        json.dumps(pkg)  # must not raise

    def test_non_serializable_state_values_are_coerced(self):
        """If the source state contains non-serializable values (e.g. a
        custom object in a seed_card field), the package must still be
        JSON-serializable — _safe_str coerces everything to str."""
        class WeirdObject:
            def __str__(self):
                return "weird"

        pkg = _assemble_final_research_package({
            "seed_cards": [{
                "seed_id": WeirdObject(),  # non-str
                "resolved_title": None,
                "existence_status": WeirdObject(),
            }],
            "tailored_method": {
                "verdict": WeirdObject(),
                "primary_baseline": {"title": WeirdObject()},
            },
        })
        # Must not raise.
        serialized = json.dumps(pkg)
        parsed = json.loads(serialized)
        # The weird object becomes its str() representation.
        assert parsed["seed_audit_summary"][0]["seed_id"] == "weird"
        assert parsed["tailor_summary"]["verdict"] == "weird"

    def test_float_confidence_serializable(self):
        """Float confidence values must serialize without precision issues."""
        pkg = _assemble_final_research_package({
            "reasoning_ledger": [
                {"decision_id": "D1", "stage": "tailor",
                 "decision": "x", "status": "proposed",
                 "confidence": 0.333333},
            ],
        })
        serialized = json.dumps(pkg)
        parsed = json.loads(serialized)
        assert parsed["ledger_entries"][0]["confidence"] == pytest.approx(0.333333)


# ── Integration: final_recommendation_node carries the package ─────────────


class TestFinalRecommendationNodeIntegration:
    def test_node_emits_final_research_package_state_field(self):
        """final_recommendation_node must write `final_research_package`
        to the state patch (top-level state field)."""
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        # Minimal legacy fields the node reads.
        state["topic"] = "steel defect detection"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        # Top-level state field.
        assert "final_research_package" in patch
        pkg = patch["final_research_package"]
        assert set(pkg.keys()) == set(EXPECTED_SECTIONS)

    def test_node_embeds_research_package_in_recommendation(self):
        """final_recommendation_node must also embed the package inside
        final_recommendation['research_package'] for convenience."""
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        state["topic"] = "test"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        rec = patch["final_recommendation"]
        assert "research_package" in rec
        # The embedded package must equal the top-level state field.
        assert rec["research_package"] == patch["final_research_package"]

    def test_node_preserves_legacy_fields(self):
        """Adding the research_package must NOT remove any legacy field
        from final_recommendation (additive, not replacing)."""
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        state["topic"] = "test"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        rec = patch["final_recommendation"]
        for legacy_key in (
            "topic", "n_papers", "n_baseline", "n_parallel",
            "n_dataset", "n_repo", "n_work_packages",
            "low_bar_status", "human_gate_status", "claim_judge_verdict",
            "verdict", "stop_reason", "notes", "research_basis",
            "artifact_id", "fused_verdict", "fused_verdict_rationale",
        ):
            assert legacy_key in rec, f"legacy field {legacy_key!r} dropped"

    # ── Re8.0 P0-A: top-level fused_verdict state fields ────────────────

    def test_p0_a_fused_verdict_top_level_field(self):
        """P0-A: final_recommendation_node must surface ``fused_verdict``
        and ``fused_verdict_rationale`` as TOP-LEVEL state patch fields,
        not only nested inside final_recommendation. Diagnostic scripts
        and the Three-Tier PASS checker read state["fused_verdict"]
        directly; without this they see null even when final_rec carries
        the correct value.
        """
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        state["topic"] = "steel defect detection"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        # P0-A: top-level state patch fields must exist.
        assert "fused_verdict" in patch
        assert "fused_verdict_rationale" in patch

    def test_p0_a_fused_verdict_matches_final_rec(self):
        """P0-A: ``patch["fused_verdict"]`` must equal the fused_verdict
        nested inside final_recommendation — they come from the same
        ``_compute_fused_verdict`` call, so they must be identical strings.
        Drift between the two would break consumers that read one or the
        other.
        """
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        state["topic"] = "steel defect detection"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        rec = patch["final_recommendation"]
        # Top-level fused_verdict must match the nested one exactly.
        assert patch["fused_verdict"] == rec["fused_verdict"]
        # Same for the rationale.
        assert patch["fused_verdict_rationale"] == rec["fused_verdict_rationale"]

    def test_p0_a_fused_verdict_rationale_non_empty(self):
        """P0-A: the top-level ``fused_verdict_rationale`` must be a
        non-empty string. An empty rationale would be a regression of
        the P0-A fix — diagnostic scripts rely on it being a meaningful
        string, not null/empty.
        """
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _full_state()
        state["topic"] = "steel defect detection"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        rationale = patch["fused_verdict_rationale"]
        assert isinstance(rationale, str)
        assert rationale.strip() != ""


# ── Re8.0 post-audit: _pkg_str list-typed work_package regression ─────────


class TestLowBarReviewListTypedWorkPackage:
    """Regression tests for commit e0239419.

    ``low_bar_review_node`` previously called ``(pkg.get("data_source") or
    "").strip().lower()``, which crashed with ``AttributeError`` when the
    work_package LLM returned a list for ``data_source`` /
    ``experiment_metrics`` / ``baseline`` / ``improved_module_source``.
    The fix added ``_pkg_str()`` helper that coerces list → joined str
    before strip. These tests pin the fix so it cannot silently regress.
    """

    def _state_with_pkg(self, pkg: dict[str, Any]) -> dict[str, Any]:
        """Minimal state that exercises low_bar_review_node's pkg loop."""
        state = _full_state()
        state["topic"] = "test topic"
        # Provide enough papers to avoid the "no verified papers" guard
        # short-circuit (which would skip the pkg loop entirely).
        state["verified_papers"] = [
            {"title": "Verified Paper One"},
            {"title": "Verified Paper Two"},
            {"title": "Verified Paper Three"},
        ]
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = [pkg]
        state["evidence_graph"] = {}
        return state

    def test_data_source_as_list_does_not_crash(self):
        """List-typed data_source must not raise AttributeError."""
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": "Verified Paper One",
            "improved_module_source": "Verified Paper Two",
            "data_source": ["NEU-DET", "GC10-DET"],  # list, not str
            "experiment_metrics": "mAP@0.5",
        }
        # Must not raise.
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        # Package should be kept (baseline + module_source are in evidence).
        assert patch["low_bar_review"]["n_packages_after_review"] == 1

    def test_experiment_metrics_as_list_does_not_crash(self):
        """List-typed experiment_metrics must not raise AttributeError."""
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": "Verified Paper One",
            "improved_module_source": "Verified Paper Two",
            "data_source": "NEU-DET",
            "experiment_metrics": ["mAP@0.5", "F1", "Precision"],  # list
        }
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        assert patch["low_bar_review"]["n_packages_after_review"] == 1

    def test_baseline_as_list_does_not_crash(self):
        """List-typed baseline must not raise AttributeError.

        Note: list-typed baseline will likely NOT match evidence_titles
        (since the joined str "verified paper one" != any title), so the
        package should be DROPPED with an issue — but no crash.
        """
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": ["YOLOv8", "Faster R-CNN"],  # list
            "improved_module_source": "Verified Paper Two",
            "data_source": "NEU-DET",
            "experiment_metrics": "mAP@0.5",
        }
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        # Package dropped because joined baseline not in evidence_titles.
        assert patch["low_bar_review"]["n_packages_after_review"] == 0
        # Issues list should mention the baseline mismatch.
        assert any("baseline" in i for i in patch["low_bar_review"]["issues"])

    def test_improved_module_source_as_list_does_not_crash(self):
        """List-typed improved_module_source must not raise."""
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": "Verified Paper One",
            "improved_module_source": ["CBAM", "BiFPN"],  # list
            "data_source": "NEU-DET",
            "experiment_metrics": "mAP@0.5",
        }
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        # Dropped because joined module_source not in evidence_titles.
        assert patch["low_bar_review"]["n_packages_after_review"] == 0

    def test_str_typed_fields_still_work_backward_compat(self):
        """Str-typed fields (the original happy path) must still work."""
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": "Verified Paper One",
            "improved_module_source": "Verified Paper Two",
            "data_source": "NEU-DET",  # str
            "experiment_metrics": "mAP@0.5",  # str
        }
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        assert patch["low_bar_review"]["n_packages_after_review"] == 1

    def test_none_typed_fields_handled(self):
        """None values (missing fields) must not raise — same as old
        ``(None or "").strip()`` behavior."""
        from apps.api.app.services.agents.graph.nodes.content import (
            low_bar_review_node,
        )

        pkg = {
            "baseline": None,
            "improved_module_source": None,
            "data_source": None,
            "experiment_metrics": None,
        }
        patch = low_bar_review_node(self._state_with_pkg(pkg))
        # All None → empty strings → no matches → package kept (empty
        # strings don't trigger the "not in evidence_titles" drop).
        assert patch["low_bar_review"]["n_packages_after_review"] == 1


# ── Re8.0 post-audit: graph topology (fulltext → paper_understanding) ────


class TestResearchGraphTopologyPostAudit:
    """Regression tests for commit 73d97fab.

    The graph node order was changed from
    ``paper_understanding → fulltext_acquisition → method_family_explorer``
    to ``fulltext_acquisition → paper_understanding → method_family_explorer``
    so that paper_understanding can parse the PDF that fulltext_acquisition
    just downloaded. These tests pin the topology so it cannot silently
    revert.
    """

    def test_fulltext_acquisition_precedes_paper_understanding(self):
        """``fulltext_acquisition`` must be an upstream neighbor of
        ``paper_understanding`` in the graph (i.e., the edge
        ``fulltext_acquisition → paper_understanding`` exists)."""
        from apps.api.app.services.agents.graph.research_graph import build_graph

        graph = build_graph().get_graph()
        edges = {(e.source, e.target) for e in graph.edges}
        # Core post-audit edge must exist.
        assert ("fulltext_acquisition", "paper_understanding") in edges, (
            "graph topology regression: fulltext_acquisition → "
            "paper_understanding edge missing (commit 73d97fab reverted?)"
        )

    def test_paper_understanding_precedes_method_family_explorer(self):
        """``paper_understanding`` must be upstream of
        ``method_family_explorer``."""
        from apps.api.app.services.agents.graph.research_graph import build_graph

        graph = build_graph().get_graph()
        edges = {(e.source, e.target) for e in graph.edges}
        assert ("paper_understanding", "method_family_explorer") in edges

    def test_old_paper_understanding_to_fulltext_edge_removed(self):
        """The old (reversed) edge ``paper_understanding → fulltext_acquisition``
        must NOT exist (commit 73d97fab removed it). If it does, the
        graph has a cycle and paper_understanding runs before PDF download."""
        from apps.api.app.services.agents.graph.research_graph import build_graph

        graph = build_graph().get_graph()
        edges = {(e.source, e.target) for e in graph.edges}
        assert ("paper_understanding", "fulltext_acquisition") not in edges, (
            "graph topology regression: old reversed edge "
            "paper_understanding → fulltext_acquisition still present"
        )

    def test_seed_audit_gate_forwards_to_fulltext_acquisition(self):
        """``seed_audit_gate`` forward target must be
        ``fulltext_acquisition`` (not ``paper_understanding`` as before
        commit 73d97fab)."""
        from apps.api.app.services.agents.graph.nodes.reflection_gates import (
            _GATE_FORWARD_TARGETS,
            GATE_SEED_AUDIT,
        )

        assert _GATE_FORWARD_TARGETS[GATE_SEED_AUDIT] == "fulltext_acquisition"

