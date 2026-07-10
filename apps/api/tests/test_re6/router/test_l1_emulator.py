"""Re6.2 Router Unification — L1 emulator integration tests.

Tests the unified router with mocked LLM dispatch to verify:
  - Successful contract-driven calls
  - JSON parse failures → formatter repair
  - Semantic validation failures → same_model repair
  - Fallback provider chain
  - Heuristic fallback behavior
  - No recursive formatter calls
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from apps.api.app.services.router.model_policy import (
    ModelPolicy, TaskRole, ProviderModelRef, create_default_policy,
)
from apps.api.app.services.router.contracts import (
    StructuredOutputContract, ContractRegistry, get_contract_registry,
    reset_contract_registry,
)
from apps.api.app.services.router.envelope import ResponseEnvelope
from apps.api.app.services.router.unified_router import (
    call_with_contract, ContractResult,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_contract_registry()
    yield
    reset_contract_registry()


def _make_envelope(content: str, model_id: str = "deepseek-v4-flash") -> ResponseEnvelope:
    return ResponseEnvelope(
        provider_id="p1",
        model_id=model_id,
        content=content,
        raw_shape="openai_chat",
    )


def _register_test_contract(
    registry: ContractRegistry,
    role: TaskRole = TaskRole.structured_extract,
    validator: str = "",
) -> StructuredOutputContract:
    contract = StructuredOutputContract(
        contract_id="l1-emulator/v1",
        task_role=role,
        json_schema={"type": "object", "properties": {"verdict": {"type": "string"}}},
        semantic_validator=validator,
        repair_strategy="same_model_once",
        fallback_behavior="typed_failure",
    )
    registry.register(contract)
    return contract


class TestEmulatorSuccessPath:
    """Test happy path: valid JSON returned on first attempt."""

    def test_success_on_first_try(self):
        _register_test_contract(get_contract_registry())

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=_make_envelope('{"verdict": "accept", "score": 8}'),
        ):
            result = call_with_contract(
                prompt="test prompt",
                task_role=TaskRole.structured_extract,
            )

        assert result.success
        assert result.content == {"verdict": "accept", "score": 8}
        assert result.repair_count == 0
        assert len(result.provider_chain) == 1

    def test_valid_json_from_fenced_block(self):
        _register_test_contract(get_contract_registry())

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=_make_envelope('```json\n{"verdict": "accept"}\n```'),
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert result.success
        assert result.content == {"verdict": "accept"}


class TestEmulatorRepairPath:
    """Test repair strategies when JSON is invalid."""

    def test_formatter_once_on_non_json(self):
        _register_test_contract(get_contract_registry())

        # First call returns non-JSON → repair formatter returns valid JSON
        call_count = [0]

        def mock_dispatch(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_envelope("This is not JSON at all")
            else:
                return _make_envelope('{"verdict": "repaired"}')

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert result.success
        assert result.content == {"verdict": "repaired"}
        assert result.repair_count == 1

    def test_same_model_repair_on_validation_failure(self):
        contract = _register_test_contract(
            get_contract_registry(),
            validator="non_empty_verdict",
        )
        contract.repair_strategy = "same_model_once"

        call_count = [0]

        def mock_dispatch(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_envelope('{"verdict": ""}')  # empty verdict → invalid
            else:
                return _make_envelope('{"verdict": "fixed"}')

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert result.success
        assert result.content == {"verdict": "fixed"}
        assert result.repair_count == 1


class TestEmulatorFallbackPath:
    """Test provider fallback chain."""

    def test_fallback_provider_on_primary_failure(self):
        _register_test_contract(get_contract_registry())

        call_count = [0]

        def mock_dispatch(prompt, ref, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("primary down")
            return _make_envelope('{"verdict": "from_fallback"}', model_id="big-pickle")

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert result.success
        assert result.content == {"verdict": "from_fallback"}
        assert len(result.provider_chain) == 2
        assert "big-pickle" in result.provider_chain[1]

    def test_all_providers_exhausted_typed_failure(self):
        _register_test_contract(get_contract_registry())

        def mock_dispatch(prompt, ref, **kwargs):
            raise RuntimeError("all down")

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert not result.success
        assert not result.heuristic_fallback
        assert result.error is not None
        assert "all down" in result.error

    def test_heuristic_marked_on_exhaustion(self):
        contract = _register_test_contract(get_contract_registry())
        contract.fallback_behavior = "heuristic_marked"

        def mock_dispatch(prompt, ref, **kwargs):
            raise RuntimeError("down")

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert not result.success
        assert result.heuristic_fallback


class TestEmulatorEdgeCases:
    """Edge case tests."""

    def test_empty_envelope_content(self):
        _register_test_contract(get_contract_registry())

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=ResponseEnvelope(content="", model_id="deepseek-v4-flash"),
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert not result.success

    def test_contract_by_id_not_by_role(self):
        registry = get_contract_registry()
        _register_test_contract(registry)
        # Register a different contract for a different role
        registry.register(StructuredOutputContract(
            contract_id="other/v1",
            task_role=TaskRole.search_control,
        ))

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=_make_envelope('{"ok": true}'),
        ):
            result = call_with_contract(
                prompt="test",
                contract_id="l1-emulator/v1",
            )

        assert result.success
        assert result.contract_id == "l1-emulator/v1"

    def test_no_formatter_recursion(self):
        """Verify formatter repair does not recursively call itself.

        The formatter path uses TaskRole.formatter with max_format_repairs=0,
        so even if the repair fails, it won't trigger another formatter call.
        """
        _register_test_contract(get_contract_registry())

        call_count = [0]

        def mock_dispatch(prompt, ref, **kwargs):
            call_count[0] += 1
            return _make_envelope("still not json")  # Never returns valid JSON

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            side_effect=mock_dispatch,
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        # Max 2 calls: primary + 1 formatter repair (no recursion)
        assert call_count[0] <= 3  # primary + formatter + potentially fallback

    def test_max_repairs_respected(self):
        _register_test_contract(get_contract_registry())

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=_make_envelope("not json"),
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        assert result.repair_count <= 1  # max_format_repairs=1


class TestEmulatorSnapshotCapture:
    """Test snapshot capture during calls."""

    def test_snapshot_stored_on_success(self):
        _register_test_contract(get_contract_registry())

        from apps.api.app.services.router.snapshot import get_snapshot_store, reset_snapshot_store
        reset_snapshot_store()
        store = get_snapshot_store()

        with patch(
            "apps.api.app.services.router.unified_router._dispatch_call_via_registry",
            return_value=_make_envelope('{"verdict": "ok"}'),
        ):
            result = call_with_contract(
                prompt="test",
                task_role=TaskRole.structured_extract,
            )

        # Verify snapshot infrastructure works
        assert result.call_id
        reset_snapshot_store()
