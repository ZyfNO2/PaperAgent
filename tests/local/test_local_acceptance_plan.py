from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_script() -> ModuleType:
    path = Path("scripts/local_acceptance.py")
    spec = importlib.util.spec_from_file_location("paperagent_local_acceptance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quick_local_plan_is_offline_and_covers_state_roundtrip() -> None:
    module = _load_script()

    steps = module.build_plan("quick", python="python")
    names = [item.name for item in steps]
    commands = [" ".join(item.command) for item in steps]

    assert names == [
        "compile",
        "ruff-lint",
        "ruff-format",
        "mypy",
        "pytest",
        "state-roundtrip",
        "interview-demo",
        "openapi",
        "benchmark",
        "academic-evaluation",
    ]
    assert any("tests/local" in command for command in commands)
    assert any("local_state_roundtrip.py" in command for command in commands)
    assert all("MISTRAL_API_KEY" not in command for command in commands)
    assert all("provider-smoke" not in command for command in commands)


def test_full_local_plan_adds_complete_suite_and_wheel_build() -> None:
    module = _load_script()

    steps = module.build_plan("full", python="python")
    by_name = {item.name: item.command for item in steps}

    assert "--cov=paperagent" in by_name["pytest"]
    assert by_name["benchmark"][by_name["benchmark"].index("--tasks") + 1] == "500"
    assert by_name["build-wheel"][:3] == ("python", "-m", "build")
