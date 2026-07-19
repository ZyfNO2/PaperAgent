from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_demo_module() -> ModuleType:
    script = Path("scripts/interview_demo.py")
    spec = importlib.util.spec_from_file_location("paperagent_interview_demo", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interview_demo_exercises_backend_contracts(tmp_path: Path) -> None:
    module = _load_demo_module()
    summary = module.run_demo(tmp_path / "paperagent.db")

    assert summary["idempotency_reused"] is True
    assert summary["idempotency_conflict_rejected"] is True
    assert summary["task_terminal"] == "succeeded"
    assert summary["event_count"] >= 6
    assert summary["review_created"] is True
    assert summary["export_created"] is True
    assert summary["export_item_count"] == 1
    assert summary["plugin_verdict"] == "GO"
    assert summary["schema_version"] == 1
    assert summary["metrics_exposed"] is True
