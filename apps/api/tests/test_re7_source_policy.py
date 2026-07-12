"""Re7.6 SourcePolicy tests — rate limiting + circuit breaker."""
from __future__ import annotations

import time
import pytest

from apps.api.app.services.retrieval.source_policy import (
    SourcePolicy, get_source_policy, reset_source_policies, _REGISTRY,
)


class TestSourcePolicy:
    def setup_method(self):
        reset_source_policies()

    def teardown_method(self):
        reset_source_policies()

    def test_acquire_release(self):
        policy = SourcePolicy("test_src", max_concurrency=2)
        assert policy.acquire(timeout_s=1.0)
        assert policy.acquire(timeout_s=1.0)
        policy.release()
        policy.release()

    def test_rate_limit_triggers_circuit_breaker(self):
        policy = SourcePolicy("test_src", circuit_breaker_threshold=3)
        for _ in range(3):
            policy.record_failure(is_rate_limit=True)
        assert policy.state == "rate_limited"
        assert not policy.acquire(timeout_s=0.1)

    def test_consecutive_success_resets_failures(self):
        policy = SourcePolicy("test_src", circuit_breaker_threshold=5)
        policy.record_failure()
        policy.record_failure()
        policy.record_success()
        assert policy._failure_count == 0
        assert policy.state == "enabled"

    def test_backoff_grows_exponentially(self):
        policy = SourcePolicy("test_src", backoff_base_s=1.0, backoff_max_s=60.0)
        policy.record_failure(is_rate_limit=True)
        first_backoff = policy._current_backoff_s
        policy.record_failure(is_rate_limit=True)
        assert policy._current_backoff_s > first_backoff

    def test_disabled_source_denies_acquire(self):
        policy = SourcePolicy("test_src", state="disabled")
        assert not policy.acquire(timeout_s=0.1)

    def test_get_source_policy_singleton(self):
        reset_source_policies()
        p1 = get_source_policy("arxiv")
        p2 = get_source_policy("arxiv")
        assert p1 is p2
        assert p1.max_concurrency == 5

    def test_semantic_scholar_has_strict_limits(self):
        reset_source_policies()
        s2 = get_source_policy("semantic_scholar")
        assert s2.max_concurrency == 1
        assert s2.circuit_breaker_threshold == 3
