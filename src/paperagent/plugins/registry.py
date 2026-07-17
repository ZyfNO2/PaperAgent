from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import cast

from paperagent.plugins.contracts import (
    PLUGIN_API_VERSION,
    PaperAgentPlugin,
    PluginError,
    PluginErrorCode,
    PluginLoadFailure,
    PluginManifest,
    PluginRequest,
    PluginResult,
)

_ENTRY_POINT_GROUP = "paperagent.plugins"


class PluginRegistry:
    def __init__(self, plugins: Iterable[PaperAgentPlugin] = ()) -> None:
        self._plugins: dict[str, PaperAgentPlugin] = {}
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: PaperAgentPlugin) -> None:
        if not isinstance(plugin, PaperAgentPlugin):
            raise PluginError(
                PluginErrorCode.MALFORMED,
                "plugin does not implement the PaperAgent plugin protocol",
            )
        manifest = plugin.manifest
        if not isinstance(manifest, PluginManifest):
            raise PluginError(
                PluginErrorCode.MALFORMED,
                "plugin manifest is not a PluginManifest instance",
            )
        if manifest.api_version != PLUGIN_API_VERSION:
            raise PluginError(
                PluginErrorCode.API_INCOMPATIBLE,
                (
                    f"plugin {manifest.name} uses API {manifest.api_version}; "
                    f"host requires {PLUGIN_API_VERSION}"
                ),
                plugin_name=manifest.name,
            )
        if manifest.name in self._plugins:
            raise PluginError(
                PluginErrorCode.DUPLICATE,
                f"duplicate plugin name: {manifest.name}",
                plugin_name=manifest.name,
            )
        self._plugins[manifest.name] = plugin

    def discover_external(
        self,
        allowed_names: set[str],
        *,
        candidates: Iterable[EntryPoint] | None = None,
    ) -> tuple[PluginLoadFailure, ...]:
        if not allowed_names:
            return ()
        selected = tuple(
            entry_points(group=_ENTRY_POINT_GROUP) if candidates is None else candidates
        )
        by_name: dict[str, list[EntryPoint]] = {}
        for candidate in selected:
            by_name.setdefault(candidate.name, []).append(candidate)

        failures: list[PluginLoadFailure] = []
        for name in sorted(allowed_names):
            matches = by_name.get(name, [])
            if not matches:
                failures.append(
                    PluginLoadFailure(
                        entry_point=name,
                        code=PluginErrorCode.NOT_FOUND,
                        message=f"authorized plugin entry point was not found: {name}",
                    )
                )
                continue
            if len(matches) != 1:
                failures.append(
                    PluginLoadFailure(
                        entry_point=name,
                        code=PluginErrorCode.DUPLICATE,
                        message=(
                            "authorized plugin entry point is ambiguous because multiple "
                            f"installed distributions expose the name: {name}"
                        ),
                    )
                )
                continue
            candidate = matches[0]
            try:
                loaded = candidate.load()
                instance = loaded() if isinstance(loaded, type) else loaded
                self.register(cast(PaperAgentPlugin, instance))
            except PluginError as exc:
                failures.append(
                    PluginLoadFailure(
                        entry_point=name,
                        code=exc.code,
                        message=exc.message,
                    )
                )
            except Exception as exc:
                failures.append(
                    PluginLoadFailure(
                        entry_point=name,
                        code=PluginErrorCode.LOAD_FAILED,
                        message=f"failed to load plugin {name}: {type(exc).__name__}",
                    )
                )
        return tuple(failures)

    def manifests(self) -> tuple[PluginManifest, ...]:
        return tuple(self._plugins[name].manifest for name in sorted(self._plugins))

    def resolve(self, name: str) -> PaperAgentPlugin:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise PluginError(
                PluginErrorCode.NOT_FOUND,
                f"plugin not found: {name}",
                plugin_name=name,
            )
        return plugin

    def invoke(self, name: str, request: PluginRequest) -> PluginResult:
        plugin = self.resolve(name)
        manifest = plugin.manifest
        if request.operation not in manifest.operations:
            raise PluginError(
                PluginErrorCode.OPERATION_UNSUPPORTED,
                f"plugin {name} does not support operation {request.operation}",
                plugin_name=name,
            )
        try:
            result = plugin.invoke(request)
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                PluginErrorCode.INVOCATION_FAILED,
                f"plugin {name} failed: {type(exc).__name__}",
                plugin_name=name,
            ) from exc
        if (
            result.plugin_name != manifest.name
            or result.plugin_version != manifest.version
            or result.request_id != request.request_id
            or result.operation != request.operation
        ):
            raise PluginError(
                PluginErrorCode.RESULT_INVALID,
                f"plugin {name} returned inconsistent result metadata",
                plugin_name=name,
            )
        return result
