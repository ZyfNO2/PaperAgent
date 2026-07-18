from __future__ import annotations

import hashlib
import json

from paperagent.plugins.contracts import (
    PluginCapability,
    PluginManifest,
    PluginRequest,
    PluginResult,
)


class EchoContractPlugin:
    _manifest = PluginManifest(
        name="echo-contract",
        version="0.7.0",
        description="Deterministic contract plugin for registry, CLI, and packaging verification.",
        capabilities=(PluginCapability.CONTRACT_TEST,),
        operations=("echo",),
        deterministic=True,
        requires_network=False,
        writes_files=False,
    )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def invoke(self, request: PluginRequest) -> PluginResult:
        canonical = json.dumps(
            request.payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output={"echo": request.payload},
            evidence={"payload_sha256": fingerprint},
        )
