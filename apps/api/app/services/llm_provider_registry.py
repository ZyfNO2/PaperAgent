"""Re5.X: Unified LLM Provider Registry — runtime-switchable providers.

Replaces the pattern where provider config is hardcoded in .env and
impossible to change at runtime. This module:

1. Loads provider configs from .env at startup (backward compatible)
2. Allows runtime registration of new providers (for frontend model switching)
3. Provides cross-provider fallback chain (when DeepSeek returns bad JSON,
   automatically try OpenCode or VOAPI to extract the right answer)
4. Each provider declares: name, api_key, base_url, model, is_reasoner

Frontend can call `POST /api/v1/llm/providers` to register a new provider,
then `POST /api/v1/llm/active` to switch the active one — no .env edit needed.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str                        # unique identifier: "deepseek", "opencode", "voapi"
    api_key: str
    base_url: str                    # will be normalized (strip trailing /v1)
    model: str                        # model name for chat/completions
    is_reasoner: bool = False         # does it return reasoning field?
    rpm_limit: int = 0               # 0 = no limit
    enabled: bool = True
    label: str = ""                  # display name for frontend
    source: str = "env"              # "env" (from .env) or "runtime" (registered at runtime)

    def to_dict(self) -> dict[str, Any]:
        """Safe dict for API (mask api_key)."""
        return {
            "name": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "is_reasoner": self.is_reasoner,
            "rpm_limit": self.rpm_limit,
            "enabled": self.enabled,
            "label": self.label or self.name,
            "source": self.source,
            "api_key_set": bool(self.api_key),
        }


@dataclass
class FallbackChain:
    """Ordered list of provider names to try."""
    primary: str
    fallbacks: list[str] = field(default_factory=list)


class ProviderRegistry:
    """Thread-safe registry of LLM providers with fallback support."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._active_chain: FallbackChain | None = None
        self._lock = threading.Lock()

    def register(self, config: ProviderConfig) -> None:
        """Register or update a provider."""
        with self._lock:
            self._providers[config.name] = config
            # If no active chain, set this as primary
            if self._active_chain is None:
                self._active_chain = FallbackChain(
                    primary=config.name,
                    fallbacks=[],
                )

    def unregister(self, name: str) -> None:
        """Remove a provider. Cannot remove the last one."""
        with self._lock:
            if name not in self._providers:
                return
            if len(self._providers) == 1:
                raise ValueError("cannot remove the last provider")
            del self._providers[name]
            if self._active_chain and self._active_chain.primary == name:
                # Pick a new primary
                new_primary = next(iter(self._providers))
                self._active_chain = FallbackChain(
                    primary=new_primary,
                    fallbacks=[n for n in self._providers if n != new_primary],
                )

    def set_active(self, primary: str, fallbacks: list[str] | None = None) -> None:
        """Set the active provider and optional fallback chain."""
        with self._lock:
            if primary not in self._providers:
                raise ValueError(f"provider '{primary}' not registered")
            self._active_chain = FallbackChain(
                primary=primary,
                fallbacks=fallbacks or [n for n in self._providers if n != primary],
            )
            logger.info("LLM active provider set to: %s (fallbacks: %s)",
                        primary, fallbacks or "auto")

    def get_active_chain(self) -> FallbackChain:
        """Get the current fallback chain."""
        with self._lock:
            if self._active_chain is None:
                raise RuntimeError("no provider registered")
            return self._active_chain

    def get_provider(self, name: str) -> ProviderConfig | None:
        with self._lock:
            return self._providers.get(name)

    def list_providers(self) -> list[ProviderConfig]:
        with self._lock:
            return list(self._providers.values())

    def get_ordered_providers(self) -> list[ProviderConfig]:
        """Get providers in fallback order: primary first, then fallbacks."""
        with self._lock:
            if self._active_chain is None:
                return list(self._providers.values())
            chain = self._active_chain
            result: list[ProviderConfig] = []
            seen: set[str] = set()
            for name in [chain.primary] + chain.fallbacks:
                cfg = self._providers.get(name)
                if cfg and cfg.enabled and name not in seen:
                    result.append(cfg)
                    seen.add(name)
            # Add any providers not in chain (shouldn't happen, but safety)
            for cfg in self._providers.values():
                if cfg.name not in seen and cfg.enabled:
                    result.append(cfg)
            return result


# ── Singleton ─────────────────────────────────────────────────────────────

_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _load_from_env(_registry)
    return _registry


def _load_from_env(registry: ProviderRegistry) -> None:
    """Load provider configs from .env (backward compatible).

    Re5.X: Only loads providers that have non-empty API keys in .env.
    Commented-out providers in .env will have empty env vars and be skipped.
    """
    # DeepSeek (primary)
    ds_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if ds_key and ds_key != "YOUR_DEEPSEEK_KEY":
        registry.register(ProviderConfig(
            name="deepseek",
            api_key=ds_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.getenv("DEEPSEEK_FLASH_MODEL", "deepseek-chat").strip(),
            is_reasoner=False,
            rpm_limit=_env_int("DEEPSEEK_RPM_LIMIT", 0),
            label="DeepSeek v4 flash",
            source="env",
        ))

    # OpenCode Zen (fallback)
    oc_key = os.getenv("OPENCODE_API_KEY", "").strip()
    if oc_key and oc_key != "YOUR_OPENCODE_KEY":
        registry.register(ProviderConfig(
            name="opencode",
            api_key=oc_key,
            base_url=os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen").strip(),
            model=os.getenv("OPENCODE_MODEL", "big-pickle").strip(),
            is_reasoner=True,
            rpm_limit=_env_int("OPENCODE_RPM_LIMIT", 0),
            label="OpenCode Zen (big-pickle)",
            source="env",
        ))

    # Mistral AI (medium, primary for verifier)
    mr_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if mr_key and mr_key != "YOUR_MISTRAL_KEY":
        registry.register(ProviderConfig(
            name="mistral",
            api_key=mr_key,
            base_url=os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai").strip(),
            model=os.getenv("MISTRAL_MODEL", "mistral-medium-latest").strip(),
            is_reasoner=False,
            rpm_limit=_env_int("MISTRAL_RPM_LIMIT", 0),
            label="Mistral Medium",
            source="env",
        ))

    # NVIDIA NIM (NV)
    nv_key = os.getenv("NV_API_KEY", "").strip()
    if nv_key:
        registry.register(ProviderConfig(
            name="nv",
            api_key=nv_key,
            base_url=os.getenv("NV_BASE_URL", "https://integrate.api.nvidia.com").strip(),
            model=os.getenv("NV_MODEL", "meta/llama-3.1-8b-instruct").strip(),
            is_reasoner=False,
            rpm_limit=_env_int("NV_RPM_LIMIT", 0),
            label="NVIDIA NIM",
            source="env",
        ))

    # Set active: deepseek primary, opencode fallback
    providers = registry.list_providers()
    if providers:
        ds = registry.get_provider("deepseek")
        if ds:
            fallback_names = [p.name for p in providers if p.name != "deepseek"]
            registry.set_active("deepseek", fallback_names)
        else:
            first = providers[0]
            fallback_names = [p.name for p in providers if p.name != first.name]
            registry.set_active(first.name, fallback_names)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def reset_provider_registry() -> None:
    """Reset registry (for tests)."""
    global _registry
    _registry = None
