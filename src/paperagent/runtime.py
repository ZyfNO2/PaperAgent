from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from paperagent.persistence import StateStore
from paperagent.providers import LLMProvider, SearchProvider
from paperagent.testing import Clock, IdFactory


@dataclass(frozen=True)
class RuntimeServices:
    llm: LLMProvider
    search: SearchProvider
    clock: Clock
    ids: IdFactory
    store: StateStore


def configurable(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not config:
        return {}
    value = config.get("configurable", {})
    if not isinstance(value, Mapping):
        raise TypeError("configurable must be a mapping")
    return value


def get_services(config: Mapping[str, Any] | None) -> RuntimeServices:
    value = configurable(config).get("services")
    if not isinstance(value, RuntimeServices):
        raise RuntimeError("RuntimeServices must be supplied in config['configurable']['services']")
    return value


def get_option(config: Mapping[str, Any] | None, name: str, default: Any) -> Any:
    return configurable(config).get(name, default)


def get_scenario(config: Mapping[str, Any] | None, default: str = "happy_path") -> str:
    return cast(str, get_option(config, "scenario", default))


def get_task_scenario(
    config: Mapping[str, Any] | None, task: str, default: str = "happy_path"
) -> str:
    options = configurable(config)
    scenarios = options.get("scenarios", {})
    if isinstance(scenarios, Mapping) and task in scenarios:
        return cast(str, scenarios[task])
    return cast(str, options.get("scenario", default))


def get_search_scenario(config: Mapping[str, Any] | None, default: str = "happy_path") -> str:
    return cast(str, get_option(config, "search_scenario", get_scenario(config, default)))


def get_fixture_version(config: Mapping[str, Any] | None) -> str:
    return cast(str, get_option(config, "fixture_version", "v0.1"))
