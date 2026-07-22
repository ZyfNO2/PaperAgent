from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("runtime_checkpoint_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_summary_tracks_partial_progress_without_false_pass() -> None:
    module = _load_script()
    summary = module._build_runtime_summary(
        cases=[{"case_id": "a"}, {"case_id": "b"}],
        dataset={"public_sha256": "sha256:test"},
        attempted_case_ids=["a"],
        completed_case_count=1,
        traces=[{"case_id": "a"}],
        errors=[],
        fatal_provider_error=None,
        prompt_records=4,
        leakage_passed=True,
        leakage_findings=[],
        allow_gold_in_workspace=False,
    )

    assert summary["completed"] == 1
    assert summary["attempted_case_ids"] == ["a"]
    assert summary["not_run_case_ids"] == ["b"]
    assert summary["passed"] is False


def test_runtime_outputs_are_rewritten_as_valid_checkpoints(tmp_path: Path) -> None:
    module = _load_script()
    summary = {"schema": "runtime", "completed": 1, "passed": False}

    module._write_runtime_outputs(
        output_dir=tmp_path,
        states=[{"case_id": "a", "state": {"status": "done"}}],
        traces=[{"case_id": "a", "terminal_status": "completed"}],
        summary=summary,
    )

    states = [
        json.loads(line)
        for line in (tmp_path / "states.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    traces = [
        json.loads(line)
        for line in (tmp_path / "run-traces.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    persisted_summary = json.loads(
        (tmp_path / "execution-summary.json").read_text(encoding="utf-8")
    )

    assert states[0]["case_id"] == "a"
    assert traces[0]["case_id"] == "a"
    assert persisted_summary == summary
