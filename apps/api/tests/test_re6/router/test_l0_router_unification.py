"""Re6.2 Router Unification — L0 unit tests.

Covers: ModelPolicy, ResponseEnvelope, StructuredOutputContract, ContractRegistry.
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# ModelPolicy
# ---------------------------------------------------------------------------


class TestModelPolicy:
    def test_valid_policy(self):
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        policy = ModelPolicy(
            role=TaskRole.structured_extract,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
            fallbacks=[
                ProviderModelRef(provider_id="p1", model_id="big-pickle"),
            ],
        )
        assert policy.role == TaskRole.structured_extract
        assert len(policy.all_refs()) == 2

    def test_rejects_disallowed_primary(self):
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        with pytest.raises(ValueError, match="not in allowed list"):
            ModelPolicy(
                role=TaskRole.structured_extract,
                primary=ProviderModelRef(provider_id="p1", model_id="gpt-4o"),
            )

    def test_rejects_disallowed_fallback(self):
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        with pytest.raises(ValueError, match="not in allowed list"):
            ModelPolicy(
                role=TaskRole.structured_extract,
                primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
                fallbacks=[
                    ProviderModelRef(provider_id="p1", model_id="claude-3"),
                ],
            )

    def test_rejects_circular_fallback(self):
        """A → B → A is a true cycle → rejected."""
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        with pytest.raises(ValueError, match="circular"):
            ModelPolicy(
                role=TaskRole.structured_extract,
                primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
                fallbacks=[
                    ProviderModelRef(provider_id="p1", model_id="big-pickle"),
                    ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
                ],
            )

    def test_self_review_allowed(self):
        """A→A (same model as primary in fallback) = self-review, allowed."""
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        policy = ModelPolicy(
            role=TaskRole.novelty_draft,
            primary=ProviderModelRef(provider_id="p1", model_id="big-pickle"),
            fallbacks=[ProviderModelRef(provider_id="p1", model_id="big-pickle")],
        )
        assert policy.is_self_review()
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        policy = ModelPolicy(
            role=TaskRole.formatter,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
            max_format_repairs=5,  # Should be capped to 1
        )
        assert policy.max_format_repairs == 1

    def test_provider_attempts_capped_at_3(self):
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        policy = ModelPolicy(
            role=TaskRole.search_control,
            primary=ProviderModelRef(provider_id="p1", model_id="deepseek-v4-flash"),
            max_provider_attempts=10,  # Should be capped to 3
        )
        assert policy.max_provider_attempts <= 3

    def test_is_self_review(self):
        from apps.api.app.services.router.model_policy import (
            ModelPolicy, TaskRole, ProviderModelRef,
        )
        # Same model in primary + fallback → self-review
        policy = ModelPolicy(
            role=TaskRole.novelty_draft,
            primary=ProviderModelRef(provider_id="p1", model_id="big-pickle"),
            fallbacks=[ProviderModelRef(provider_id="p1", model_id="big-pickle")],
        )
        assert policy.is_self_review()

    def test_create_default_policy(self):
        from apps.api.app.services.router.model_policy import (
            create_default_policy, TaskRole, ALLOWED_MODEL_IDS,
        )
        policy = create_default_policy(TaskRole.evidence_critic)
        assert policy.primary.model_id == "big-pickle"
        assert len(policy.fallbacks) == 1
        assert policy.fallbacks[0].model_id in ALLOWED_MODEL_IDS

    def test_provider_model_ref_rejects(self):
        from apps.api.app.services.router.model_policy import ProviderModelRef
        with pytest.raises(ValueError, match="not in allowed list"):
            ProviderModelRef(provider_id="p1", model_id="unsupported-model")


# ---------------------------------------------------------------------------
# ResponseEnvelope
# ---------------------------------------------------------------------------


class TestResponseEnvelope:
    def test_from_openai_normalization(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        raw = {
            "model": "deepseek-v4-flash",
            "id": "req-001",
            "choices": [{
                "message": {"role": "assistant", "content": '{"key": "value"}'},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        env = ResponseEnvelope.from_openai(raw, provider_id="p1")
        assert env.raw_shape == "openai_chat"
        assert env.model_id == "deepseek-v4-flash"
        assert env.content == '{"key": "value"}'
        assert env.usage.input_tokens == 10
        assert env.usage.output_tokens == 20

    def test_from_anthropic_normalization(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        raw = {
            "model": "big-pickle",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello"},
                "finish_reason": "end_turn",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 15},
            "reasoning": "I think...",
        }
        env = ResponseEnvelope.from_anthropic(raw, provider_id="p1")
        assert env.raw_shape == "anthropic_message"
        assert env.usage.output_tokens == 15
        assert env.reasoning == "I think..."

    def test_has_valid_json_true(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content='{"a": 1}')
        assert env.has_valid_json_content()

    def test_has_valid_json_fenced(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content='```json\n{"b": 2}\n```')
        assert env.has_valid_json_content()

    def test_has_valid_json_false(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content="not json at all")
        assert not env.has_valid_json_content()

    def test_extract_json(self):
        from apps.api.app.services.router.envelope import ResponseEnvelope
        env = ResponseEnvelope(content='{"ok": true}')
        extracted = env.extract_json()
        assert extracted == {"ok": True}


# ---------------------------------------------------------------------------
# StructuredOutputContract + Registry
# ---------------------------------------------------------------------------


class TestContractRegistry:
    def test_register_and_retrieve(self):
        from apps.api.app.services.router.contracts import (
            StructuredOutputContract, ContractRegistry, TaskRole,
        )
        registry = ContractRegistry()
        contract = StructuredOutputContract(
            contract_id="test-contract/v1",
            task_role=TaskRole.structured_extract,
            json_schema={"type": "object", "properties": {"title": {"type": "string"}}},
        )
        registry.register(contract)
        assert registry.get_by_id("test-contract/v1") is contract
        assert registry.get_by_role(TaskRole.structured_extract) is contract

    def test_version_uniqueness(self):
        """Registering a new contract for the same task_role supersedes the old one."""
        from apps.api.app.services.router.contracts import (
            StructuredOutputContract, ContractRegistry, TaskRole,
        )
        registry = ContractRegistry()
        v1 = StructuredOutputContract(
            contract_id="test/v1", task_role=TaskRole.search_control,
            json_schema={"type": "object"},
        )
        v2 = StructuredOutputContract(
            contract_id="test/v2", task_role=TaskRole.search_control,
            json_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        registry.register(v1)
        registry.register(v2)
        # v2 should be active for the role
        assert registry.get_by_role(TaskRole.search_control) is v2
        # v1 still accessible by ID
        assert registry.get_by_id("test/v1") is v1

    def test_unregister(self):
        from apps.api.app.services.router.contracts import (
            StructuredOutputContract, ContractRegistry, TaskRole,
        )
        registry = ContractRegistry()
        contract = StructuredOutputContract(
            contract_id="to-remove/v1", task_role=TaskRole.rag_answer,
        )
        registry.register(contract)
        assert registry.unregister("to-remove/v1")
        assert registry.get_by_id("to-remove/v1") is None
        assert registry.get_by_role(TaskRole.rag_answer) is None

    def test_list_roles(self):
        from apps.api.app.services.router.contracts import (
            StructuredOutputContract, ContractRegistry, TaskRole,
        )
        registry = ContractRegistry()
        registry.register(StructuredOutputContract(
            contract_id="a/v1", task_role=TaskRole.evidence_critic,
        ))
        registry.register(StructuredOutputContract(
            contract_id="b/v1", task_role=TaskRole.novelty_draft,
        ))
        roles = registry.list_roles()
        assert TaskRole.evidence_critic in roles
        assert TaskRole.novelty_draft in roles
