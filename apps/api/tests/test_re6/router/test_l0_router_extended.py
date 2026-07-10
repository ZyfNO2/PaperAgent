"""Re6.2 Router Unification — L0 extended unit tests.

Covers: ContractResult, SnapshotStore, validators, repair strategies.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# ContractResult
# ---------------------------------------------------------------------------

class TestContractResult:
    def test_success_result(self):
        from apps.api.app.services.router.unified_router import ContractResult
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content='{"key": "value"}', model_id="deepseek-v4-flash")
        result = ContractResult(
            success=True,
            content={"key": "value"},
            envelope=env,
            contract_id="test/v1",
            repair_count=0,
            provider_chain=["p1/deepseek-v4-flash"],
            call_id="call-001",
        )
        assert result.success
        assert not result.is_heuristic
        assert result.content_json == {"key": "value"}

    def test_failure_result(self):
        from apps.api.app.services.router.unified_router import ContractResult
        result = ContractResult(
            success=False,
            error="all providers exhausted",
            contract_id="test/v1",
            provider_chain=["p1/d1", "p1/d2"],
            repair_count=1,
            call_id="call-002",
        )
        assert not result.success
        assert result.content is None
        assert result.provider_chain == ["p1/d1", "p1/d2"]

    def test_heuristic_fallback(self):
        from apps.api.app.services.router.unified_router import ContractResult
        result = ContractResult(
            success=False,
            heuristic_fallback=True,
            content={"partial": True},
            contract_id="test/v1",
            call_id="call-003",
        )
        assert result.is_heuristic
        assert not result.success

    def test_content_json_from_envelope(self):
        from apps.api.app.services.router.unified_router import ContractResult
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content='{"nested": true}')
        result = ContractResult(
            success=False,
            content=None,
            envelope=env,
            contract_id="test/v1",
            call_id="call-004",
        )
        assert result.content_json == {"nested": True}

    def test_content_json_prefers_content(self):
        from apps.api.app.services.router.unified_router import ContractResult
        result = ContractResult(
            success=True,
            content={"direct": "value"},
            contract_id="test/v1",
            call_id="call-005",
        )
        assert result.content_json == {"direct": "value"}


# ---------------------------------------------------------------------------
# SnapshotStore
# ---------------------------------------------------------------------------

class TestSnapshotStore:
    def test_save_and_get(self):
        from apps.api.app.services.router.snapshot import (
            RunModelSnapshot, SnapshotStore,
        )
        store = SnapshotStore()
        snap = RunModelSnapshot(
            snapshot_id="snap-001",
            call_id="call-001",
            contract_id="test/v1",
            success=True,
        )
        store.save(snap)
        retrieved = store.get("call-001")
        assert retrieved is not None
        assert retrieved.snapshot_id == "snap-001"

    def test_list_all_sorted(self):
        from apps.api.app.services.router.snapshot import (
            RunModelSnapshot, SnapshotStore,
        )
        store = SnapshotStore()
        snap1 = RunModelSnapshot(
            snapshot_id="snap-a", call_id="a",
            timestamp="2026-01-01T00:00:00", contract_id="c1",
        )
        snap2 = RunModelSnapshot(
            snapshot_id="snap-b", call_id="b",
            timestamp="2026-01-02T00:00:00", contract_id="c1",
        )
        store.save(snap2)
        store.save(snap1)
        all_snaps = store.list_all()
        assert all_snaps[0].call_id == "a"
        assert all_snaps[1].call_id == "b"

    def test_list_by_role(self):
        from apps.api.app.services.router.snapshot import (
            RunModelSnapshot, SnapshotStore,
        )
        store = SnapshotStore()
        store.save(RunModelSnapshot(
            snapshot_id="s1", call_id="a", contract_role="extract",
            contract_id="c1",
        ))
        store.save(RunModelSnapshot(
            snapshot_id="s2", call_id="b", contract_role="critic",
            contract_id="c2",
        ))
        store.save(RunModelSnapshot(
            snapshot_id="s3", call_id="c", contract_role="extract",
            contract_id="c3",
        ))
        extracts = store.list_by_role("extract")
        assert len(extracts) == 2
        assert {s.contract_role for s in store.list_by_role("critic")} == {"critic"}

    def test_stats(self):
        from apps.api.app.services.router.snapshot import (
            RunModelSnapshot, SnapshotStore,
        )
        store = SnapshotStore()
        store.save(RunModelSnapshot(
            snapshot_id="s1", call_id="a", contract_id="c1",
            success=True, token_input=100, token_output=50,
        ))
        store.save(RunModelSnapshot(
            snapshot_id="s2", call_id="b", contract_id="c2",
            success=False, token_input=200, token_output=0, error="fail",
        ))
        stats = store.stats()
        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["failure"] == 1
        assert stats["total_tokens_in"] == 300
        assert stats["total_tokens_out"] == 50

    def test_clear(self):
        from apps.api.app.services.router.snapshot import (
            RunModelSnapshot, SnapshotStore,
        )
        store = SnapshotStore()
        store.save(RunModelSnapshot(
            snapshot_id="s1", call_id="a", contract_id="c1",
        ))
        store.clear()
        assert store.stats()["total"] == 0

    def test_capture_classmethod(self):
        from apps.api.app.services.router.snapshot import RunModelSnapshot
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        from apps.api.app.services.router.contracts import StructuredOutputContract
        from apps.api.app.services.router.envelope import ResponseEnvelope

        policy = ModelPolicy(
            role=TaskRole.structured_extract,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
            fallbacks=[ProviderModelRef(provider_id="p2", model_id="big-pickle")],
        )
        contract = StructuredOutputContract(
            contract_id="test/v1", task_role=TaskRole.structured_extract,
        )
        env = ResponseEnvelope(content="{}", model_id="deepseek-v4-flash", provider_id="p1")

        snap = RunModelSnapshot.capture(
            call_id="call-capture",
            policy=policy,
            contract=contract,
            provider_chain=["p1/deepseek-v4-flash"],
            repair_count=0,
            success=True,
            envelope=env,
            prompt_sha256="abc123",
        )
        assert snap.call_id == "call-capture"
        assert snap.policy_role == "structured_extract"
        assert snap.contract_id == "test/v1"
        assert snap.success
        assert snap.repair_count == 0

    def test_snapshot_immutable(self):
        from apps.api.app.services.router.snapshot import RunModelSnapshot
        snap = RunModelSnapshot(
            snapshot_id="s1", call_id="a", contract_id="c1", success=True,
        )
        with pytest.raises(Exception):
            snap.success = False  # frozen model

    def test_to_summary_dict(self):
        from apps.api.app.services.router.snapshot import RunModelSnapshot
        snap = RunModelSnapshot(
            snapshot_id="s1", call_id="a", contract_id="c1",
            contract_role="structured_extract", success=True,
        )
        summary = snap.to_summary_dict()
        assert summary["snapshot_id"] == "s1"
        assert summary["success"] is True


# ---------------------------------------------------------------------------
# Semantic validators
# ---------------------------------------------------------------------------

class TestBuiltinValidators:
    def test_non_empty_verdict_pass(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("non_empty_verdict")
        assert fn is not None
        ok, err = fn({"verdict": "accept"})
        assert ok
        assert err is None

    def test_non_empty_verdict_missing(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("non_empty_verdict")
        ok, err = fn({})
        assert not ok
        assert "missing" in err

    def test_non_empty_verdict_empty(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("non_empty_verdict")
        ok, err = fn({"verdict": ""})
        assert not ok

    def test_has_innovation_points_pass(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("has_innovation_points")
        ok, err = fn({"innovation_points": [{"id": 1, "text": "test"}]})
        assert ok

    def test_has_innovation_points_empty(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("has_innovation_points")
        ok, err = fn({"innovation_points": []})
        assert not ok

    def test_has_work_packages_pass(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("has_work_packages")
        ok, err = fn({"work_packages": [{"name": "WP1"}]})
        assert ok

    def test_has_work_packages_missing(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("has_work_packages")
        ok, err = fn({})
        assert not ok

    def test_valid_score_range_pass(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("valid_score_range")
        ok, _ = fn({"score": 7.5})
        assert ok

    def test_valid_score_range_out_of_bounds(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("valid_score_range")
        ok, err = fn({"score": 15})
        assert not ok
        assert "out of range" in err

    def test_valid_overall_verdict_pass(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("valid_overall_verdict")
        for v in ("ACCEPT", "MINOR_REVISION", "REJECT"):
            ok, err = fn({"overall_verdict": v})
            assert ok, f"{v} should be valid"

    def test_valid_overall_verdict_invalid(self):
        from apps.api.app.services.router.validators import get_validator
        fn = get_validator("valid_overall_verdict")
        ok, err = fn({"overall_verdict": "MAYBE"})
        assert not ok

    def test_list_validators(self):
        from apps.api.app.services.router.validators import list_validators
        names = list_validators()
        assert "non_empty_verdict" in names
        assert "has_innovation_points" in names
        assert "has_work_packages" in names
        assert "valid_score_range" in names
        assert "valid_overall_verdict" in names
        assert "non_empty_narrative" in names

    def test_register_validator_decorator(self):
        from apps.api.app.services.router.validators import (
            register_validator, get_validator,
        )

        @register_validator("_test_custom")
        def custom_fn(data):
            return len(data) > 0, "empty" if len(data) == 0 else None

        fn = get_validator("_test_custom")
        assert fn is not None
        ok, _ = fn({"a": 1})
        assert ok
        ok, err = fn({})
        assert not ok
        assert err == "empty"


# ---------------------------------------------------------------------------
# Repair strategies (unit tests without LLM dispatch)
# ---------------------------------------------------------------------------

class TestRepairStrategies:
    def test_execute_repair_strategy_fail(self):
        from apps.api.app.services.router.repair import execute_repair_strategy
        from apps.api.app.services.router.contracts import StructuredOutputContract
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        from apps.api.app.services.router.envelope import ResponseEnvelope

        contract = StructuredOutputContract(
            contract_id="test/v1",
            task_role=TaskRole.structured_extract,
            repair_strategy="fail",
        )
        policy = ModelPolicy(
            role=TaskRole.structured_extract,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
        )
        env = ResponseEnvelope(content="bad json")

        result = execute_repair_strategy(
            "fail",
            prompt="test",
            envelope=env,
            contract=contract,
            policy=policy,
        )
        assert result is None

    def test_unknown_strategy_returns_none(self):
        from apps.api.app.services.router.repair import execute_repair_strategy
        from apps.api.app.services.router.contracts import StructuredOutputContract
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        from apps.api.app.services.router.envelope import ResponseEnvelope

        contract = StructuredOutputContract(
            contract_id="test/v1", task_role=TaskRole.structured_extract,
        )
        policy = ModelPolicy(
            role=TaskRole.structured_extract,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
        )
        env = ResponseEnvelope(content="{}")

        result = execute_repair_strategy(
            "unknown_strategy",  # type: ignore
            prompt="test",
            envelope=env,
            contract=contract,
            policy=policy,
        )
        assert result is None


# ---------------------------------------------------------------------------
# call_json_contract convenience wrapper
# ---------------------------------------------------------------------------

class TestCallJsonContract:
    def test_raises_on_no_contract(self):
        from apps.api.app.services.router.unified_router import call_json_contract
        from apps.api.app.services.router.model_policy import TaskRole

        with pytest.raises(ValueError, match="no contract found"):
            call_json_contract(
                "test prompt",
                task_role=TaskRole.structured_extract,
            )

    def test_call_with_contract_requires_contract_or_role(self):
        from apps.api.app.services.router.unified_router import call_with_contract
        with pytest.raises(ValueError, match="no contract found"):
            call_with_contract(prompt="test")
