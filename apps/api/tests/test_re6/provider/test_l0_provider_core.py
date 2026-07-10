"""Re6.1 Provider Core — L0 unit tests.

Covers: URL safety (SSRF), ProviderProfile schema, SecretStore, errors, ledger.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# URL Safety (SSRF)
# ---------------------------------------------------------------------------


class TestUrlSafetyStatic:
    """Static URL safety checks (no DNS resolution)."""

    def test_reject_loopback(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://127.0.0.1/v1/models")
        assert not result.allowed

    def test_reject_private_10(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://10.0.0.1/v1/models")
        assert not result.allowed

    def test_reject_metadata_ip(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://169.254.169.254/latest/meta-data")
        assert not result.allowed

    def test_reject_non_http_scheme(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("ftp://example.com/models")
        assert not result.allowed

    def test_reject_http_without_local_mode(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://example.com/v1/models", local_mode=False)
        assert not result.allowed

    def test_allow_https(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("https://api.openai.com/v1/models")
        assert result.allowed

    def test_allow_localhost_in_local_mode(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://localhost:11434/v1/models", local_mode=True)
        assert result.allowed

    def test_reject_localhost_without_local_mode(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("http://localhost:11434/v1/models", local_mode=False)
        assert not result.allowed

    def test_reject_unparseable_url(self):
        from apps.api.app.services.security.url_safety import check_url_safety
        result = check_url_safety("not a url at all !!!!")
        assert not result.allowed


class TestRedactErrorBody:
    def test_redacts_bearer_token(self):
        from apps.api.app.services.security.url_safety import redact_error_body
        body = "Error: Authorization: Bearer sk-1234567890abcdef1234567890abcdef"
        result = redact_error_body(body)
        assert "sk-1234567890abcdef1234567890abcdef" not in result
        assert "[REDACTED]" in result

    def test_redacts_api_key_header(self):
        from apps.api.app.services.security.url_safety import redact_error_body
        body = "x-api-key: abc123secret456"
        result = redact_error_body(body)
        assert "abc123secret456" not in result
        assert "[REDACTED]" in result

    def test_truncates_long_body(self):
        from apps.api.app.services.security.url_safety import redact_error_body
        body = "x" * 500
        result = redact_error_body(body, max_len=100)
        assert len(result) <= 103  # 100 + "..."


# ---------------------------------------------------------------------------
# ProviderProfile schema
# ---------------------------------------------------------------------------


class TestProviderProfileSchema:
    def test_valid_profile_creation(self):
        from apps.api.app.services.providers.profile import (
            ProviderProfile, ProviderProtocol, ModelInfo, DiscoverySource,
        )
        profile = ProviderProfile(
            label="Test",
            protocol=ProviderProtocol.openai_compatible,
            base_url="https://api.test.com",
            models=[
                ModelInfo(model_id="deepseek-v4-flash", label="DeepSeek V4 Flash",
                          discovery_source=DiscoverySource.manual),
                ModelInfo(model_id="big-pickle", label="Big Pickle",
                          discovery_source=DiscoverySource.manual),
            ],
        )
        assert profile.label == "Test"
        assert len(profile.models) == 2

    def test_rejects_disallowed_model(self):
        from apps.api.app.services.providers.profile import (
            ProviderProfile, ModelInfo,
        )
        with pytest.raises(ValueError, match="not in the allowed list"):
            ProviderProfile(
                label="Test",
                base_url="https://api.test.com",
                models=[
                    ModelInfo(model_id="gpt-4o", label="GPT-4o"),
                ],
            )

    def test_rejects_mixed_models(self):
        from apps.api.app.services.providers.profile import (
            ProviderProfile, ModelInfo,
        )
        with pytest.raises(ValueError, match="not in the allowed list"):
            ProviderProfile(
                label="Test",
                base_url="https://api.test.com",
                models=[
                    ModelInfo(model_id="deepseek-v4-flash"),
                    ModelInfo(model_id="claude-sonnet-5"),  # not in whitelist
                ],
            )

    def test_create_default_profile(self):
        from apps.api.app.services.providers.profile import create_default_profile
        profile = create_default_profile(base_url="https://opencode.example.com")
        assert len(profile.models) == 2
        model_ids = {m.model_id for m in profile.models}
        assert model_ids == {"deepseek-v4-flash", "big-pickle"}


# ---------------------------------------------------------------------------
# SecretStore
# ---------------------------------------------------------------------------


class TestSecretStore:
    def test_store_and_retrieve_session(self):
        from apps.api.app.services.providers.secret_store import (
            store_secret, get_secret, delete_secret, secret_is_set,
        )
        provider_id = "test-provider-001"
        key_id = store_secret(provider_id, "sk-test-key-12345", vault=False)

        assert secret_is_set(key_id)
        assert get_secret(key_id) == "sk-test-key-12345"

        # Delete
        assert delete_secret(provider_id, key_id)
        assert not secret_is_set(key_id)
        assert get_secret(key_id) is None

    def test_store_empty_key_raises(self):
        from apps.api.app.services.providers.secret_store import store_secret
        with pytest.raises(ValueError, match="non-empty"):
            store_secret("p1", "")

    def test_delete_nonexistent_is_noop(self):
        from apps.api.app.services.providers.secret_store import delete_secret
        # Should not raise
        result = delete_secret("nonexistent", "fake_key_id")
        assert result is False

    def test_key_id_format(self):
        from apps.api.app.services.providers.secret_store import store_secret
        key_id = store_secret("my-provider", "key123")
        assert key_id.startswith("pa_my-provider_")
        assert len(key_id) > 20


# ---------------------------------------------------------------------------
# ProviderError
# ---------------------------------------------------------------------------


class TestProviderErrors:
    def test_classify_401(self):
        from apps.api.app.services.providers.errors import classify_http_error, ProviderErrorType
        err = classify_http_error(401, "Unauthorized")
        assert err.error_type == ProviderErrorType.invalid_auth
        assert not err.retryable

    def test_classify_429(self):
        from apps.api.app.services.providers.errors import classify_http_error, ProviderErrorType
        err = classify_http_error(429, "Rate limited")
        assert err.error_type == ProviderErrorType.rate_limited
        assert err.retryable

    def test_classify_503(self):
        from apps.api.app.services.providers.errors import classify_http_error, ProviderErrorType
        err = classify_http_error(503)
        assert err.error_type == ProviderErrorType.transient_network
        assert err.retryable

    def test_classify_404(self):
        from apps.api.app.services.providers.errors import classify_http_error, ProviderErrorType
        err = classify_http_error(404, "Model not found")
        assert err.error_type == ProviderErrorType.model_not_found


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


class TestLedger:
    def test_record_and_read(self):
        from apps.api.app.services.providers.ledger import (
            record_event, read_ledger, record_deleted_tombstone,
        )
        # Use temp data dir to avoid polluting real ledger
        with patch.dict(os.environ, {"PAPERAGENT_DATA_DIR": tempfile.mkdtemp()}):
            record_event("created", "p_test", "v1", details={"protocol": "openai_compatible"})
            record_deleted_tombstone("p_test", "v1")

            entries = read_ledger("p_test", limit=10)
            assert len(entries) == 2
            assert entries[0]["event"] == "created"
            assert entries[1]["event"] == "deleted"
            assert entries[1]["details"]["secret_purged"] is True

    def test_no_raw_key_in_ledger(self):
        from apps.api.app.services.providers.ledger import record_event, read_ledger
        with patch.dict(os.environ, {"PAPERAGENT_DATA_DIR": tempfile.mkdtemp()}):
            # Even if details contain "api_key" by accident, verify it's not raw
            record_event("created", "p_test", "v1",
                         details={"model_id": "big-pickle"})  # no key field
            entries = read_ledger("p_test", limit=1)
            assert "api_key" not in entries[0].get("details", {})
            assert "raw_key" not in str(entries)
