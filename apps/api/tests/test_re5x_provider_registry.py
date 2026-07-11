"""Re5.X: Provider registry + LLM API tests."""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestProviderRegistry:
    def test_loads_from_env(self):
        """Registry should load providers from .env at startup."""
        from apps.api.app.services.llm_provider_registry import get_provider_registry
        registry = get_provider_registry()
        providers = registry.list_providers()
        # At least deepseek should be loaded from .env
        names = [p.name for p in providers]
        assert "deepseek" in names

    def test_get_ordered_providers(self):
        """Ordered providers should have primary first."""
        from apps.api.app.services.llm_provider_registry import get_provider_registry
        registry = get_provider_registry()
        chain = registry.get_active_chain()
        ordered = registry.get_ordered_providers()
        assert ordered[0].name == chain.primary

    def test_register_runtime_provider(self):
        """Can register a new provider at runtime."""
        from apps.api.app.services.llm_provider_registry import (
            get_provider_registry, ProviderConfig,
        )
        registry = get_provider_registry()
        registry.register(ProviderConfig(
            name="test-provider",
            api_key="test-key",
            base_url="https://test.example.com",
            model="test-model",
            source="runtime",
        ))
        cfg = registry.get_provider("test-provider")
        assert cfg is not None
        assert cfg.model == "test-model"
        assert cfg.source == "runtime"

    def test_set_active(self):
        """Can switch active provider."""
        from apps.api.app.services.llm_provider_registry import get_provider_registry
        registry = get_provider_registry()
        providers = registry.list_providers()
        if len(providers) >= 2:
            second = providers[1].name
            registry.set_active(second)
            chain = registry.get_active_chain()
            assert chain.primary == second

    def test_provider_to_dict_masks_key(self):
        """to_dict should not expose api_key."""
        from apps.api.app.services.llm_provider_registry import ProviderConfig
        cfg = ProviderConfig(
            name="test", api_key="secret-key-123",
            base_url="https://test.com", model="test",
        )
        d = cfg.to_dict()
        assert "api_key" not in d
        assert d["api_key_set"] is True


class TestLLMApi:
    def test_list_providers(self):
        """GET /api/v1/llm/providers returns provider list."""
        resp = client.get("/api/v1/llm/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert data["n"] >= 1
        assert "active_primary" in data

    def test_set_active_without_permission(self):
        """POST /active without write header should be denied."""
        resp = client.post("/api/v1/llm/active", json={"primary": "deepseek"})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "PERMISSION_DENIED"

    def test_set_active_with_permission(self):
        """POST /active with write header should switch."""
        # Get current providers
        resp = client.get("/api/v1/llm/providers")
        providers = resp.json()["providers"]
        if len(providers) >= 1:
            name = providers[0]["name"]
            resp = client.post("/api/v1/llm/active",
                              json={"primary": name},
                              headers={"X-ACP-Capability": "write"})
            data = resp.json()
            assert data["success"] is True
            assert data["active_primary"] == name

    def test_register_provider_without_permission(self):
        """POST /providers without write header should be denied."""
        resp = client.post("/api/v1/llm/providers", json={
            "name": "test", "api_key": "k", "base_url": "https://t.com", "model": "m",
        })
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "PERMISSION_DENIED"
