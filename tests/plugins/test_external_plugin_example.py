from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

from paperagent.plugins import PluginRegistry, PluginRequest

EXAMPLE = Path("examples/external_plugin")


def _load_module() -> ModuleType:
    path = EXAMPLE / "src" / "paperagent_interview_plugin" / "__init__.py"
    spec = importlib.util.spec_from_file_location("paperagent_interview_plugin", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_plugin_distribution_declares_entry_point() -> None:
    metadata = tomllib.loads((EXAMPLE / "pyproject.toml").read_text(encoding="utf-8"))
    entry_points = metadata["project"]["entry-points"]["paperagent.plugins"]

    assert entry_points == {
        "interview-summary": "paperagent_interview_plugin:InterviewSummaryPlugin"
    }


def test_external_plugin_obeys_host_contract() -> None:
    module = _load_module()
    registry = PluginRegistry((module.InterviewSummaryPlugin(),))

    result = registry.invoke(
        "interview-summary",
        PluginRequest(
            request_id="interview-plugin-test",
            operation="summarize",
            payload={"points": ["idempotency", "bounded retries", "durable events"]},
        ),
    )

    assert result.output == {
        "count": 3,
        "summary": "idempotency | bounded retries | durable events",
    }
