from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_benchmark_module() -> ModuleType:
    script = Path("scripts/repository_benchmark.py")
    spec = importlib.util.spec_from_file_location("paperagent_repository_benchmark", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_benchmark_reports_reproducible_shape(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    result = module.run_benchmark(tmp_path / "benchmark.db", 12)

    assert result["task_count"] == 12
    assert result["claimed_count"] == 12
    assert result["database_size_bytes"] > 0
    assert result["create"]["p50_ms"] >= 0
    assert result["create"]["p95_ms"] >= result["create"]["p50_ms"]
    assert result["claim"]["p95_ms"] >= result["claim"]["p50_ms"]
    assert "not a distributed" in result["boundary"]
