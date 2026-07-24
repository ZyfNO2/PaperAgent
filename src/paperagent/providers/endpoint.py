from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from paperagent.providers.base import LLMProvider


class EndpointProtocol(StrEnum):
    OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"
    MISTRAL_CHAT_COMPLETIONS = "mistral_chat_completions"


class EndpointHealthState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class EndpointCapabilities:
    native_json_schema: bool | None = None
    json_object: bool | None = None
    prompt_injected_schema: bool = True
    tool_calling: bool | None = None


@dataclass(frozen=True, slots=True)
class EndpointLimits:
    max_concurrency: int = 1
    requests_per_minute: int | None = None
    request_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        if self.requests_per_minute is not None and self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class EndpointConfig:
    endpoint_id: str
    vendor: str
    protocol: EndpointProtocol
    model: str
    base_url: str
    api_key_env: str | None = None
    capabilities: EndpointCapabilities = field(default_factory=EndpointCapabilities)
    limits: EndpointLimits = field(default_factory=EndpointLimits)
    failure_threshold: int = 2
    cooldown_seconds: float = 30.0
    disabled: bool = False

    def __post_init__(self) -> None:
        for name, value in {
            "endpoint_id": self.endpoint_id,
            "vendor": self.vendor,
            "model": self.model,
            "base_url": self.base_url,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RoutedEndpoint:
    config: EndpointConfig
    provider: LLMProvider


@dataclass(frozen=True, slots=True)
class ProviderPool:
    pool_id: str
    endpoints: tuple[RoutedEndpoint, ...]

    def __post_init__(self) -> None:
        if not self.pool_id.strip():
            raise ValueError("pool_id must be non-empty")
        if not self.endpoints:
            raise ValueError("provider pool must contain at least one endpoint")
        endpoint_ids = [endpoint.config.endpoint_id for endpoint in self.endpoints]
        if len(endpoint_ids) != len(set(endpoint_ids)):
            raise ValueError("endpoint IDs must be unique within a provider pool")


__all__ = [
    "EndpointCapabilities",
    "EndpointConfig",
    "EndpointHealthState",
    "EndpointLimits",
    "EndpointProtocol",
    "ProviderPool",
    "RoutedEndpoint",
]
