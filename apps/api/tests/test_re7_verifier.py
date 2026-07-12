"""Re7.6 Verifier Emulator Regression Tests.

Tests that the verifier correctly handles empty, malformed, and edge-case LLM
outputs — ensuring zero coverage is never silently treated as success.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.verify import (
    _normalise_verifier_output,
    _assign_candidate_ids,
)


# ---------------------------------------------------------------------------
# _normalise_verifier_output edge cases
# ---------------------------------------------------------------------------

class TestNormaliseVerifierOutput:
    """Re7.2 §2.4: JSON list, object wrapper, reasoning JSON, Markdown JSON."""

    def test_none_returns_empty(self):
        assert _normalise_verifier_output(None) == []

    def test_empty_string_returns_empty(self):
        assert _normalise_verifier_output("") == []

    def test_empty_list_returns_empty(self):
        assert _normalise_verifier_output("[]") == []

    def test_valid_json_array(self):
        raw = json.dumps([
            {"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "c2", "verdict": "reject", "relation_to_topic": "none", "reason": "unrelated"},
        ])
        result = _normalise_verifier_output(raw)
        assert len(result) == 2
        assert result[0]["candidate_id"] == "c1"
        assert result[1]["verdict"] == "reject"

    def test_markdown_fenced_json(self):
        raw = '```json\n[{"candidate_id":"c1","verdict":"accept","relation_to_topic":"baseline","reason":"ok"}]\n```'
        result = _normalise_verifier_output(raw)
        assert len(result) == 1
        assert result[0]["verdict"] == "accept"

    def test_reasoning_then_json(self):
        raw = '<think>Let me evaluate each paper carefully...</think>\n[{"candidate_id":"c1","verdict":"reject","relation_to_topic":"none","reason":"unrelated"}]'
        result = _normalise_verifier_output(raw)
        assert len(result) == 1
        assert result[0]["candidate_id"] == "c1"

    def test_dict_with_verdicts_key(self):
        raw = {"verdicts": [{"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"}]}
        result = _normalise_verifier_output(raw)
        assert len(result) == 1
        assert result[0]["verdict"] == "accept"

    def test_dict_with_candidates_key(self):
        raw = {"candidates": [{"candidate_id": "c1", "verdict": "weak_reject", "relation_to_topic": "survey", "reason": "related"}]}
        result = _normalise_verifier_output(raw)
        assert len(result) == 1

    def test_dict_with_results_key(self):
        raw = {"results": [{"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "parallel", "reason": "ok"}]}
        result = _normalise_verifier_output(raw)
        assert len(result) == 1

    def test_plain_dict_single_verdict(self):
        raw = {"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"}
        result = _normalise_verifier_output(raw)
        assert len(result) == 1
        assert result[0]["verdict"] == "accept"

    def test_list_of_dicts_direct(self):
        raw = [
            {"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "c2", "verdict": "reject", "relation_to_topic": "none", "reason": "unrelated"},
        ]
        result = _normalise_verifier_output(raw)
        assert len(result) == 2

    def test_garbage_text_returns_empty(self):
        raw = "I cannot evaluate these papers because I am a language model."
        assert _normalise_verifier_output(raw) == []

    def test_integer_returns_empty(self):
        assert _normalise_verifier_output(42) == []

    def test_bytes_input(self):
        raw = b'[{"candidate_id":"c1","verdict":"accept","relation_to_topic":"baseline","reason":"ok"}]'
        result = _normalise_verifier_output(raw)
        assert len(result) == 1

    def test_empty_dict_returns_empty(self):
        assert _normalise_verifier_output({}) == []

    def test_dict_without_known_keys_returns_empty(self):
        assert _normalise_verifier_output({"foo": "bar"}) == []


# ---------------------------------------------------------------------------
# _assign_candidate_ids stability
# ---------------------------------------------------------------------------

class TestAssignCandidateIds:
    def test_stable_ids(self):
        candidates = [
            {"title": "Paper A", "doi": "10.1234/a"},
            {"title": "Paper B"},
            {"title": "Paper C"},
        ]
        result = _assign_candidate_ids(candidates)
        ids = [c["candidate_id"] for c in result]
        assert len(set(ids)) == 3
        assert all(id_.startswith("10.1234/a") or id_.startswith("Paper") or id_.startswith("cand_") for id_ in ids)

    def test_preserves_existing_ids(self):
        candidates = [{"title": "P", "candidate_id": "custom_id"}]
        result = _assign_candidate_ids(candidates)
        assert result[0]["candidate_id"] == "custom_id"

    def test_index_fallback(self):
        candidates = [{}, {}]
        result = _assign_candidate_ids(candidates)
        assert result[0]["candidate_id"] == "cand_0"
        assert result[1]["candidate_id"] == "cand_1"


# ---------------------------------------------------------------------------
# Emulator-based: verify_node with mocked LLM
# ---------------------------------------------------------------------------

def _make_contract_result(content: list | None, *, success: bool = True,
                           heuristic_fallback: bool = False, error: str | None = None,
                           provider: str = "mock", model: str = "mock-model"):
    """Build a mock ContractResult for unified router tests."""
    from apps.api.app.services.router.unified_router import ContractResult
    return ContractResult(
        success=success,
        content=content,
        contract_id="verification-batch/v1",
        provider_chain=[provider, model],
        heuristic_fallback=heuristic_fallback,
        error=error,
    )


class TestVerifyNodeEmulator:
    """Re7.6 §2.4: verify_node must classify failures correctly under emulator conditions.

    Re7.7 disabled USE_CONTRACT_PATH by default (default="0"). These tests
    mock call_with_contract_list, so they MUST opt-in to the contract path
    via the autouse fixture below — otherwise the mock is bypassed and the
    real llm_router.call_json is called, producing non-deterministic results.
    """

    PATCH_TARGET = "apps.api.app.services.router.call_with_contract_list"

    @pytest.fixture(autouse=True)
    def _enable_contract_path(self, monkeypatch):
        """Force USE_CONTRACT_PATH=1 so the mocked contract path is actually used."""
        monkeypatch.setenv("USE_CONTRACT_PATH", "1")

    def _make_state(self, n_candidates: int = 4) -> dict:
        """Create a minimal ResearchState for verify_node."""
        return {
            "topic": "Vision Transformer for steel surface defect detection",
            "topic_atoms": {
                "method": ["vision transformer", "ViT"],
                "object": ["steel surface"],
                "task": ["defect detection"],
                "dataset_terms": ["NEU-DET", "GC10-DET"],
            },
            "paper_candidates": [
                {
                    "title": f"Defect Detection Method {i}",
                    "candidate_id": f"defect_vit_{i}",
                    "abstract": f"Proposes a vision transformer approach for detecting defects on steel surfaces using dataset {i}.",
                    "doi": f"10.1234/defect{i}",
                    "source": "arxiv",
                    "url": f"https://arxiv.org/abs/2601.{i:04d}",
                }
                for i in range(n_candidates)
            ],
            "verify_scope": "search",
            "citation_expansion_done": False,
            "trace_events": [],
            "errors": [],
        }

    def test_zero_output_classified_as_verification_failed(self):
        """Re7.6 SOP: LLM returns empty list → verification_failed, not silent 0 papers."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=4)
        with patch(self.PATCH_TARGET, return_value=_make_contract_result([])):
            result = verify_node(state)

        errors = result.get("errors", [])
        assert any(e.get("error") == "verification_failed" for e in errors), f"expected verification_failed error, got {errors}"
        trace_events = result.get("trace_events", [])
        assert trace_events, "expected trace_events"
        ts = trace_events[0].get("output_summary", {})
        assert ts.get("verification_failed") is True, f"expected verification_failed=True in trace, got {ts}"
        assert ts.get("verification_status") == "zero_coverage"
        assert ts.get("contract_id") == "verification-batch/v1"

    def test_partial_coverage_detected(self):
        """Re7.6 SOP: 12 candidates, 4 resolved → partial_coverage, not silent drop."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=6)

        call_count = 0
        def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_contract_result([
                {"candidate_id": "defect_vit_0", "verdict": "accept", "relation_to_topic": "parallel", "reason": "ok"},
                {"candidate_id": "defect_vit_1", "verdict": "reject", "relation_to_topic": "none", "reason": "unrelated"},
            ])

        with patch(self.PATCH_TARGET, side_effect=mock_call):
            result = verify_node(state)

        errors = result.get("errors", [])
        has_partial = any(e.get("error") == "partial_coverage" for e in errors)
        trace_events = result.get("trace_events", [])
        ts = trace_events[0].get("output_summary", {}) if trace_events else {}
        assert has_partial or ts.get("verification_status") == "partial_coverage"

    def test_full_coverage_classified_correctly(self):
        """Re7.6 SOP: all 4 resolved → full_coverage."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=4)

        def mock_call(*args, **kwargs):
            return _make_contract_result([
                {"candidate_id": f"defect_vit_{i}", "verdict": "accept" if i % 2 == 0 else "reject",
                 "relation_to_topic": "baseline", "reason": "ok"}
                for i in range(4)
            ])

        with patch(self.PATCH_TARGET, side_effect=mock_call):
            result = verify_node(state)

        trace_events = result.get("trace_events", [])
        ts = trace_events[0].get("output_summary", {}) if trace_events else {}
        assert ts.get("verification_status") == "full_coverage"
        assert ts.get("coverage") == 1.0
        verified = result.get("verified_papers", [])
        assert len(verified) == 2

    def test_all_reject_not_misclassified_as_failure(self):
        """Re7.6 §2.4: '12 candidates + all reject' → 'verified_zero_accept', NOT failure."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=3)

        def mock_call(*args, **kwargs):
            return _make_contract_result([
                {"candidate_id": f"defect_vit_{i}", "verdict": "reject",
                 "relation_to_topic": "none", "reason": "unrelated"}
                for i in range(3)
            ])

        with patch(self.PATCH_TARGET, side_effect=mock_call):
            result = verify_node(state)

        errors = result.get("errors", [])
        assert not any(e.get("error") == "verification_failed" for e in errors)
        trace_events = result.get("trace_events", [])
        ts = trace_events[0].get("output_summary", {}) if trace_events else {}
        assert ts.get("verification_status") == "full_coverage"
        assert ts.get("n_accept") == 0

    def test_llm_exception_triggers_verification_failed(self):
        """Re7.6 SOP: LLM raises → verification_failed, candidates quarantined."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=3)

        def mock_call(*args, **kwargs):
            raise RuntimeError("LLM connection timeout")

        def mock_legacy(*args, **kwargs):
            # Legacy fallback also fails; verify_node should surface verification_failed.
            raise RuntimeError("legacy unavailable")

        with patch(self.PATCH_TARGET, side_effect=mock_call):
            with patch("apps.api.app.services.llm_router.call_json", side_effect=mock_legacy):
                result = verify_node(state)

        errors = result.get("errors", [])
        assert any("LLMUnavailable" in e.get("error", "") or "verification_failed" in e.get("error", "") for e in errors)

    def test_invalid_ids_not_accepted(self):
        """Re7.6 §2.4: unknown candidate IDs → filtered out, not accepted."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=2)

        def mock_call(*args, **kwargs):
            return _make_contract_result([
                {"candidate_id": "defect_vit_0", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
                {"candidate_id": "UNKNOWN_ID_999", "verdict": "accept", "relation_to_topic": "none", "reason": "fake"},
            ])

        with patch(self.PATCH_TARGET, side_effect=mock_call):
            result = verify_node(state)

        verified = result.get("verified_papers", [])
        accepted = [v for v in verified if v.get("verdict") == "accept"]
        assert len(accepted) == 1
        assert accepted[0].get("candidate_id") == "defect_vit_0"
        assert not any(v.get("candidate_id") == "UNKNOWN_ID_999" for v in accepted)
        trace_events = result.get("trace_events", [])
        ts = trace_events[0].get("output_summary", {}) if trace_events else {}
        assert ts.get("verification_status") == "partial_coverage"

    def test_candidates_preserved_on_failure(self):
        """Re7.6 §2.4: when LLM fails, original candidate data not lost."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=3)

        def mock_legacy(*args, **kwargs):
            # Legacy fallback also fails; candidates must be preserved as unresolved.
            raise RuntimeError("legacy unavailable")

        with patch(self.PATCH_TARGET, return_value=_make_contract_result(None, success=False, error="empty output")):
            with patch("apps.api.app.services.llm_router.call_json", side_effect=mock_legacy):
                result = verify_node(state)

        verified = result.get("verified_papers", [])
        assert len(verified) == 3
        for v in verified:
            assert v.get("verdict") == "unresolved"

    def test_legacy_fallback_used_when_contract_fails(self):
        """Re7.6: legacy llm_router.call_json is used as one-time fallback."""
        from apps.api.app.services.agents.graph.nodes.verify import verify_node

        state = self._make_state(n_candidates=2)

        def mock_contract(*args, **kwargs):
            raise RuntimeError("contract unavailable")

        def mock_legacy(*args, **kwargs):
            return [
                {"candidate_id": "defect_vit_0", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
                {"candidate_id": "defect_vit_1", "verdict": "reject", "relation_to_topic": "none", "reason": "unrelated"},
            ]

        with patch(self.PATCH_TARGET, side_effect=mock_contract):
            with patch("apps.api.app.services.llm_router.call_json", side_effect=mock_legacy):
                result = verify_node(state)

        trace_events = result.get("trace_events", [])
        ts = trace_events[0].get("output_summary", {}) if trace_events else {}
        assert ts.get("verification_status") == "full_coverage"
        assert ts.get("contract_id") == "legacy_fallback"


# ---------------------------------------------------------------------------
# Re7.6 P0-2: unified_router path (feature-flagged)
# ---------------------------------------------------------------------------

class TestVerifyUnifiedRouter:
    """Tests for the unified_router contract path (now default)."""

    def _make_state(self, n_candidates: int = 3) -> dict:
        return {
            "topic": "Vision Transformer for steel surface defect detection",
            "topic_atoms": {"method": ["ViT"], "object": ["steel"], "task": ["detection"], "dataset_terms": ["NEU"]},
            "paper_candidates": [
                {
                    "title": f"Paper {i}", "candidate_id": f"cand_{i}",
                    "abstract": f"Vision transformer for defects {i}", "source": "arxiv",
                }
                for i in range(n_candidates)
            ],
            "verify_scope": "search", "citation_expansion_done": False,
            "trace_events": [], "errors": [],
        }

    def test_contract_registered(self):
        """Register the verification-batch/v1 contract and verify its properties."""
        from apps.api.app.services.router import get_contract_registry, reset_contract_registry
        reset_contract_registry()
        from apps.api.app.services.router.register_verification import register_verification_contract
        register_verification_contract()
        reg = get_contract_registry()
        contract = reg.get_by_id("verification-batch/v1")
        assert contract is not None
        assert contract.task_role.value == "structured_extract"
        assert contract.semantic_validator == "verification_batch"
        assert contract.repair_strategy == "formatter_once"
        assert contract.max_repairs == 1
        reset_contract_registry()

    def test_validator_rejects_invalid_verdict(self):
        """verification_batch validator: invalid verdicts are rejected."""
        import importlib
        import apps.api.app.services.router.validators as _v_mod
        importlib.reload(_v_mod)
        from apps.api.app.services.router.validators.verification_validator import validate_verification_batch

        data = [
            {"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "c2", "verdict": "bogus_value", "relation_to_topic": "none", "reason": "x"},
        ]
        is_valid, error = validate_verification_batch(data)
        assert not is_valid
        assert "bogus" in error.lower()

    def test_validator_accepts_valid_batch(self):
        from apps.api.app.services.router.validators.verification_validator import validate_verification_batch
        data = [
            {"candidate_id": "c1", "verdict": "accept", "relation_to_topic": "baseline", "reason": "ok"},
            {"candidate_id": "c2", "verdict": "reject", "relation_to_topic": "none", "reason": "unrelated"},
        ]
        is_valid, error = validate_verification_batch(data)
        assert is_valid, f"expected valid, got error: {error}"

    def test_validator_rejects_missing_candidate_id(self):
        from apps.api.app.services.router.validators.verification_validator import validate_verification_batch
        data = [{"verdict": "accept", "relation_to_topic": "baseline"}]
        is_valid, error = validate_verification_batch(data)
        assert not is_valid
