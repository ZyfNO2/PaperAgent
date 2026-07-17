from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PLUGIN_API_VERSION = "v0.7"


def _validate_json_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string mapping key")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(f"{path} contains a non-JSON-compatible value: {type(value).__name__}")


class PluginCapability(StrEnum):
    CONTRACT_TEST = "contract_test"
    RESEARCH_METHOD = "research_method"
    EVALUATION = "evaluation"
    EXPORT = "export"


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_version: str = PLUGIN_API_VERSION
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
    description: str = Field(min_length=1, max_length=500)
    capabilities: tuple[PluginCapability, ...]
    operations: tuple[str, ...]
    deterministic: bool
    requires_network: bool = False
    writes_files: bool = False

    @field_validator("capabilities", "operations")
    @classmethod
    def require_unique_non_empty_values(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if not value:
            raise ValueError("at least one value is required")
        if len(set(value)) != len(value):
            raise ValueError("values must be unique")
        return value

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for operation in value:
            if not operation or not operation.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"invalid plugin operation: {operation!r}")
        return value


class PluginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=64)
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, object]) -> dict[str, object]:
        _validate_json_value(value, path="payload")
        return value


class PluginResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin_name: str
    plugin_version: str
    request_id: str
    operation: str
    output: dict[str, object]
    warnings: tuple[str, ...] = ()
    evidence: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_json_fields(self) -> PluginResult:
        _validate_json_value(self.output, path="output")
        _validate_json_value(self.evidence, path="evidence")
        return self


class PluginErrorCode(StrEnum):
    NOT_FOUND = "not_found"
    DUPLICATE = "duplicate"
    API_INCOMPATIBLE = "api_incompatible"
    MALFORMED = "malformed"
    LOAD_FAILED = "load_failed"
    OPERATION_UNSUPPORTED = "operation_unsupported"
    INVOCATION_FAILED = "invocation_failed"
    RESULT_INVALID = "result_invalid"


class PluginError(Exception):
    def __init__(
        self,
        code: PluginErrorCode,
        message: str,
        *,
        plugin_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.plugin_name = plugin_name


class PluginLoadFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_point: str
    code: PluginErrorCode
    message: str


@runtime_checkable
class PaperAgentPlugin(Protocol):
    @property
    def manifest(self) -> PluginManifest: ...

    def invoke(self, request: PluginRequest) -> PluginResult: ...
