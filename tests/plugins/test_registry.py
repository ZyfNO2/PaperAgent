from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from paperagent.plugins import (
    EchoContractPlugin,
    PluginCapability,
    PluginError,
    PluginErrorCode,
    PluginManifest,
    PluginRegistry,
    PluginRequest,
    PluginResult,
    build_default_registry,
)


class ExternalTestPlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="external-test",
            version="1.0.0",
            description="external registry test plugin",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("echo",),
            deterministic=True,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output={"ok": True},
        )


class FakeEntryPoint:
    def __init__(self, name: str, loaded: Any) -> None:
        self.name = name
        self._loaded = loaded

    def load(self) -> Any:
        return self._loaded


def test_default_registry_has_stable_builtin_order() -> None:
    registry, failures = build_default_registry()

    assert failures == ()
    assert tuple(manifest.name for manifest in registry.manifests()) == (
        "academic-method-tailoring",
        "echo-contract",
    )


def test_registry_rejects_duplicate_name() -> None:
    registry = PluginRegistry((EchoContractPlugin(),))

    with pytest.raises(PluginError) as captured:
        registry.register(EchoContractPlugin())

    assert captured.value.code is PluginErrorCode.DUPLICATE


def test_external_discovery_loads_only_explicit_name() -> None:
    registry = PluginRegistry()
    candidates = (FakeEntryPoint("external-test", ExternalTestPlugin),)

    failures = registry.discover_external(
        {"external-test"},
        candidates=candidates,  # type: ignore[arg-type]
    )

    assert failures == ()
    assert registry.resolve("external-test").manifest.version == "1.0.0"


def test_external_discovery_reports_missing_authorized_name() -> None:
    registry = PluginRegistry()

    failures = registry.discover_external(
        {"missing-plugin"},
        candidates=(),
    )

    assert failures[0].code is PluginErrorCode.NOT_FOUND
    assert registry.manifests() == ()


def test_external_discovery_rejects_duplicate_entry_point_names() -> None:
    registry = PluginRegistry()
    candidates = (
        FakeEntryPoint("external-test", ExternalTestPlugin),
        FakeEntryPoint("external-test", ExternalTestPlugin),
    )

    failures = registry.discover_external(
        {"external-test"},
        candidates=candidates,  # type: ignore[arg-type]
    )

    assert len(failures) == 1
    assert failures[0].code is PluginErrorCode.DUPLICATE
    assert registry.manifests() == ()


def test_registry_rejects_unsupported_operation() -> None:
    registry = PluginRegistry((EchoContractPlugin(),))

    with pytest.raises(PluginError) as captured:
        registry.invoke(
            "echo-contract",
            PluginRequest(request_id="request-1", operation="missing", payload={}),
        )

    assert captured.value.code is PluginErrorCode.OPERATION_UNSUPPORTED


def test_plugin_request_rejects_non_json_payload() -> None:
    with pytest.raises(ValidationError, match="non-JSON-compatible"):
        PluginRequest(
            request_id="request-1",
            operation="echo",
            payload={"bad": object()},
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_plugin_request_rejects_non_finite_json_numbers(value: float) -> None:
    with pytest.raises(ValidationError, match="non-finite float"):
        PluginRequest(
            request_id="request-1",
            operation="echo",
            payload={"bad": value},
        )
