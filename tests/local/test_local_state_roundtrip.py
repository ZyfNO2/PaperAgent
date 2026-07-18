from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_script(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_state_roundtrip_preserves_state_and_recovers_inflight(
    tmp_path: Path,
) -> None:
    module = _load_script(
        "paperagent_local_state_roundtrip", "scripts/local_state_roundtrip.py"
    )

    summary = module.run_local_state_roundtrip(tmp_path)

    assert summary["status"] == "passed"
    assert summary["review_restored"] is True
    assert summary["export_sha256"] == summary["restored_export_sha256"]
    assert len(summary["backup_sha256"]) == 64
    assert summary["restart_recovery_code"] == "PROCESS_RESTARTED"
    assert summary["restored_task_total"] == 1
    assert summary["journal_mode"] == "wal"
