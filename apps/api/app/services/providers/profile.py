"""ProviderProfile Pydantic v2 schema for Re6.1 Provider Core.

Defines the data model for a registered LLM provider including its
protocol, models, capabilities, and secret reference (no raw key).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Global model whitelist (Re6.X constraint)
# ---------------------------------------------------------------------------

_ALLOWED_MODEL_IDS: frozenset[str] = frozenset({"deepseek-v4-flash", "big-pickle"})


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class SecretRefType(str, Enum):
    session = "session"          # stored in process memory only
    local_vault = "local_vault"  # stored in OS keyring or encrypted file


class SecretRef(BaseModel):
    """Reference to a stored API key — never the key itself."""
    type: SecretRefType = SecretRefType.session
    key_id: str = Field(default_factory=lambda: uuid4().hex)
    api_key_set: bool = False


class ProviderProtocol(str, Enum):
    openai_compatible = "openai_compatible"
    anthropic_like = "anthropic_like"


class DiscoverySource(str, Enum):
    auto = "auto"
    manual = "manual"


class ProviderStatus(str, Enum):
    active = "active"
    invalid = "invalid"
    disabled = "disabled"


class ProbedCapabilities(BaseModel):
    """Results of model capability probing."""
    chat: bool = False
    json_object: bool = False
    json_schema: bool = False
    reasoning_envelope: bool = False
    streaming: bool = False
    probed_at: datetime | None = None
    probe_error: str | None = None


class ModelInfo(BaseModel):
    """Information about a specific model on this provider."""
    model_id: str
    label: str | None = None
    discovery_source: DiscoverySource = DiscoverySource.manual
    probed_capabilities: ProbedCapabilities | None = None


class ProviderCapabilities(BaseModel):
    """Aggregate capabilities for a provider."""
    supports_chat: bool = False
    supports_json_object: bool = False
    supports_json_schema: bool = False
    supports_reasoning: bool = False
    supports_streaming: bool = False
    discovery_supported: bool = True
    max_context_tokens: int | None = None


# ---------------------------------------------------------------------------
# Main profile schema
# ---------------------------------------------------------------------------

class ProviderProfile(BaseModel):
    """A registered LLM provider profile.

    This is the primary data model for provider management.
    Raw API keys are NEVER stored in this model — only SecretRef.
    """
    provider_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    label: str = ""
    protocol: ProviderProtocol = ProviderProtocol.openai_compatible
    base_url: str = ""
    secret_ref: SecretRef = Field(default_factory=SecretRef)
    models: list[ModelInfo] = Field(default_factory=list)
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    status: ProviderStatus = ProviderStatus.active
    config_version: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _validate_model_whitelist(self) -> "ProviderProfile":
        """Re6.X constraint: models must be in the global whitelist."""
        for m in self.models:
            if m.model_id not in _ALLOWED_MODEL_IDS:
                raise ValueError(
                    f"model_id '{m.model_id}' is not in the allowed list: "
                    f"{sorted(_ALLOWED_MODEL_IDS)}. "
                    "Only deepseek-v4-flash and big-pickle are supported."
                )
        return self

    @model_validator(mode="after")
    def _validate_base_url(self) -> "ProviderProfile":
        """Basic structural validation on base_url."""
        if self.base_url:
            url = self.base_url.strip()
            if not url.startswith(("https://", "http://")):
                raise ValueError(f"base_url must start with https:// or http://: {url}")
            if url.endswith("/"):
                self.base_url = url.rstrip("/")
        return self

    def touch_version(self) -> None:
        """Increment config_version and updated_at on mutation."""
        self.config_version = uuid4().hex
        self.updated_at = datetime.now(timezone.utc)

    def api_view(self) -> dict[str, Any]:
        """Return a JSON-safe view suitable for GET API responses.

        Never includes the raw API key — only api_key_set flag.
        """
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_default_profile(
    label: str = "Default OpenCode Proxy",
    base_url: str = "",
    protocol: ProviderProtocol = ProviderProtocol.openai_compatible,
) -> ProviderProfile:
    """Create a ProviderProfile pre-populated with the two allowed models."""
    return ProviderProfile(
        label=label,
        protocol=protocol,
        base_url=base_url,
        models=[
            ModelInfo(
                model_id="deepseek-v4-flash",
                label="DeepSeek V4 Flash",
                discovery_source=DiscoverySource.manual,
            ),
            ModelInfo(
                model_id="big-pickle",
                label="Big Pickle",
                discovery_source=DiscoverySource.manual,
            ),
        ],
        capabilities=ProviderCapabilities(),
    )
