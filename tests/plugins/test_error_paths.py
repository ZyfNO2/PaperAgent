from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from paperagent.plugins import (
    PLUGIN_API_VERSION,
    EchoContractPlugin,
    PluginCapability,
    PluginError,
    PluginErrorCode,
    PluginManifest,
    PluginRegistry,
    PluginRequest,
    PluginResult,
)


class _MalformedPlugin:
    manifest = {"name": "malformed"}

    def invoke(self, request: PluginRequest) -> PluginResult:
        raise AssertionError(request)


class _IncompatiblePlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            api_version="v9",
            name="incompatible-plugin",
            version="1.0.0",
            description="incompatible API test plugin",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("run",),
            deterministic=True,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        raise AssertionError(request)


class _RaisingPlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="raising-plugin",
            version="1.0.0",
            description="raises during invocation",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("run",),
            deterministic=True,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        raise RuntimeError(request.request_id)


class _InconsistentPlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="inconsistent-plugin",
            version="1.0.0",
            description="returns inconsistent result metadata",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("run",),
            deterministic=True,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        return PluginResult(
            plugin_name="wrong-plugin",
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output={},
        )


class _FakeEntryPoint:
    def __init__(self, name: str, loaded: Any = None, error: Exception | None = None) -> None:
        self.name = name
        self._loaded = loaded
        self._error = error

    def load(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._loaded


def test_registry_rejects_non_protocol_object() -> None:
    with pytest.raises(PluginError, match="does not implement") as captured:
        PluginRegistry((object(),))  # type: ignore[arg-type]

    assert captured.value.code is PluginErrorCode.MALFORMED


def test_registry_rejects_non_manifest_value() -> None:
    registry = PluginRegistry()

    with pytest.raises(PluginError, match="PluginManifest") as captured:
        registry.register(_MalformedPlugin())  # type: ignore[arg-type]

    assert captured.value.code is PluginErrorCode.MALFORMED


def test_registry_rejects_incompatible_api() -> None:
    registry = PluginRegistry()

    with pytest.raises(PluginError, match=PLUGIN_API_VERSION) as captured:
        registry.register(_IncompatiblePlugin())

    assert captured.value.code is PluginErrorCode.API_INCOMPATIBLE


def test_external_discovery_isolates_plugin_and_loader_failures() -> None:
    registry = PluginRegistry((EchoContractPlugin(),))
    failures = registry.discover_external(
        {"duplicate", "broken-loader"},
        candidates=(
            _FakeEntryPoint("duplicate", EchoContractPlugin()),
            _FakeEntryPoint("broken-loader", error=RuntimeError("boom")),
        ),  # type: ignore[arg-type]
    )

    assert [failure.code for failure in failures] == [
        PluginErrorCode.LOAD_FAILED,
        PluginErrorCode.DUPLICATE,
    ]


def test_resolve_missing_plugin_is_typed() -> None:
    with pytest.raises(PluginError, match="not found") as captured:
        PluginRegistry().resolve("missing-plugin")

    assert captured.value.code is PluginErrorCode.NOT_FOUND


def test_invoke_wraps_unexpected_plugin_failure() -> None:
    registry = PluginRegistry((_RaisingPlugin(),))

    with pytest.raises(PluginError, match="RuntimeError") as captured:
        registry.invoke(
            "raising-plugin",
            PluginRequest(request_id="request-1", operation="run", payload={}),
        )

    assert captured.value.code is PluginErrorCode.INVOCATION_FAILED


def test_invoke_rejects_inconsistent_result_metadata() -> None:
    registry = PluginRegistry((_InconsistentPlugin(),))

    with pytest.raises(PluginError, match="inconsistent") as captured:
        registry.invoke(
            "inconsistent-plugin",
            PluginRequest(request_id="request-1", operation="run", payload={}),
        )

    assert captured.value.code is PluginErrorCode.RESULT_INVALID


def test_manifest_rejects_duplicates_and_invalid_operation() -> None:
    with pytest.raises(ValidationError, match="unique"):
        PluginManifest(
            name="duplicate-values",
            version="1.0.0",
            description="duplicate values",
            capabilities=(PluginCapability.CONTRACT_TEST, PluginCapability.CONTRACT_TEST),
            operations=("run",),
            deterministic=True,
        )

    with pytest.raises(ValidationError, match="invalid plugin operation"):
        PluginManifest(
            name="invalid-operation",
            version="1.0.0",
            description="invalid operation",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("not valid",),
            deterministic=True,
        )


def test_request_rejects_nested_non_string_mapping_key() -> None:
    with pytest.raises(ValidationError, match="non-string mapping key"):
        PluginRequest(
            request_id="request-1",
            operation="run",
            payload={"nested": {1: "bad"}},  # type: ignore[dict-item]
        )
