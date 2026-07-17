from paperagent.plugins.academic_method import (
    MethodAuditReport,
    MethodPlan,
    method_plan_template,
)
from paperagent.plugins.academic_method_guard import (
    AcademicMethodTailoringPlugin,
    audit_method_plan,
)
from paperagent.plugins.contracts import (
    PLUGIN_API_VERSION,
    PaperAgentPlugin,
    PluginCapability,
    PluginError,
    PluginErrorCode,
    PluginLoadFailure,
    PluginManifest,
    PluginRequest,
    PluginResult,
)
from paperagent.plugins.echo import EchoContractPlugin
from paperagent.plugins.registry import PluginRegistry


def build_default_registry(
    *,
    allowed_external_names: set[str] | None = None,
) -> tuple[PluginRegistry, tuple[PluginLoadFailure, ...]]:
    registry = PluginRegistry((EchoContractPlugin(), AcademicMethodTailoringPlugin()))
    failures = registry.discover_external(allowed_external_names or set())
    return registry, failures


__all__ = [
    "PLUGIN_API_VERSION",
    "AcademicMethodTailoringPlugin",
    "EchoContractPlugin",
    "MethodAuditReport",
    "MethodPlan",
    "PaperAgentPlugin",
    "PluginCapability",
    "PluginError",
    "PluginErrorCode",
    "PluginLoadFailure",
    "PluginManifest",
    "PluginRegistry",
    "PluginRequest",
    "PluginResult",
    "audit_method_plan",
    "build_default_registry",
    "method_plan_template",
]
