from __future__ import annotations

from paperagent.plugins import (
    PluginCapability,
    PluginManifest,
    PluginRequest,
    PluginResult,
)


class InterviewSummaryPlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="interview-summary",
            version="0.1.0",
            description="Return a deterministic summary of supplied interview talking points.",
            capabilities=(PluginCapability.CONTRACT_TEST,),
            operations=("summarize",),
            deterministic=True,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        raw_points = request.payload.get("points", [])
        points = [str(item).strip() for item in raw_points] if isinstance(raw_points, list) else []
        normalized = [item for item in points if item]
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output={
                "count": len(normalized),
                "summary": " | ".join(normalized),
            },
        )


__all__ = ["InterviewSummaryPlugin"]
