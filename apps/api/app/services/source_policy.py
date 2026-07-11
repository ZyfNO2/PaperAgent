"""Unified SourcePolicy — controls per-source enable/disable, concurrency, backoff.

When a source is disabled, NO HTTP request is made — including citation expansion.
The policy is the single gate that all adapters and citation_expander must consult.

Inspired by AutoResearchClaw's per-source TTL/cache_key pattern (MIT, B-level reuse)
and Draftpaper passport.py's append-only ledger concept (NC, B-level reuse).
All code is independently written for PaperAgent.
"""
from __future__ import annotations

import os
from typing import Any

# Default sensitive sources (high 429 risk)
_SENSITIVE_SOURCES = {"semantic_scholar", "openalex"}

# Per-source defaults
_SOURCE_DEFAULTS: dict[str, dict[str, Any]] = {
    "arxiv":            {"concurrency": 5, "timeout": 15, "retries": 2},
    "crossref":         {"concurrency": 3, "timeout": 15, "retries": 2},
    "github":           {"concurrency": 3, "timeout": 15, "retries": 1},
    "openalex":         {"concurrency": 2, "timeout": 20, "retries": 3},
    "semantic_scholar": {"concurrency": 2, "timeout": 10, "retries": 3},
    "huggingface":      {"concurrency": 3, "timeout": 15, "retries": 1},
    "core":             {"concurrency": 3, "timeout": 15, "retries": 1},
}


class SourcePolicy:
    """Per-source policy: enabled, concurrency, backoff, status tracking."""

    def __init__(self) -> None:
        self._enabled: dict[str, bool] = {}
        self._concurrency: dict[str, int] = {}
        self._retries: dict[str, int] = {}
        self._timeout: dict[str, int] = {}
        self._statuses: dict[str, str] = {}

        env_disabled = os.getenv("RATE_LIMITED_SOURCES_DISABLED", "").lower()
        disable_sensitive = env_disabled in ("1", "true", "yes") or os.getenv(
            "TEST_MODE", ""
        ).lower() in ("1", "true")

        for source, defaults in _SOURCE_DEFAULTS.items():
            is_sensitive = source in _SENSITIVE_SOURCES
            env_key = f"{source.upper()}_ENABLED"
            env_val = os.getenv(env_key)

            if env_val is not None:
                enabled = env_val.lower() in ("1", "true", "yes")
            elif is_sensitive and disable_sensitive:
                enabled = False
            else:
                enabled = True

            self._enabled[source] = enabled
            self._concurrency[source] = defaults["concurrency"]
            self._retries[source] = defaults["retries"]
            self._timeout[source] = defaults["timeout"]
            self._statuses[source] = "enabled" if enabled else "skipped"

    def is_enabled(self, source: str) -> bool:
        return self._enabled.get(source, True)

    def skip(self, source: str) -> None:
        """Mark source as skipped (disabled, no request made)."""
        self._enabled[source] = False
        self._statuses[source] = "skipped"

    def mark_rate_limited(self, source: str) -> None:
        self._statuses[source] = "rate_limited"

    def mark_failed(self, source: str) -> None:
        self._statuses[source] = "failed"

    def mark_ok(self, source: str) -> None:
        self._statuses[source] = "enabled"

    def status(self, source: str) -> str:
        return self._statuses.get(source, "enabled")

    def concurrency(self, source: str) -> int:
        return self._concurrency.get(source, 3)

    def retries(self, source: str) -> int:
        return self._retries.get(source, 1)

    def timeout(self, source: str) -> int:
        return self._timeout.get(source, 15)

    def summary(self) -> dict[str, dict[str, Any]]:
        """Full status summary for UI/trace."""
        return {
            s: {
                "enabled": self._enabled.get(s, True),
                "status": self.status(s),
                "concurrency": self.concurrency(s),
                "retries": self.retries(s),
                "timeout": self.timeout(s),
            }
            for s in _SOURCE_DEFAULTS
        }


# Singleton
_policy: SourcePolicy | None = None


def get_source_policy() -> SourcePolicy:
    global _policy
    if _policy is None:
        _policy = SourcePolicy()
    return _policy


def reset_source_policy() -> None:
    """Reset policy (for tests)."""
    global _policy
    _policy = None
