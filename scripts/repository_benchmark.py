from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from paperagent.api import SQLiteTaskRepository, TaskCreateRequest
from paperagent.schemas.request import ResearchRequest


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values) * 1000, 3),
        "p95_ms": round(_percentile(values, 0.95) * 1000, 3),
        "max_ms": round(max(values, default=0.0) * 1000, 3),
    }


def run_benchmark(database: Path, task_count: int) -> dict[str, Any]:
    if task_count < 1:
        raise ValueError("task_count must be positive")
    repository = SQLiteTaskRepository(database)
    payload = TaskCreateRequest(
        request=ResearchRequest(question="How should an agent repository be benchmarked?")
    )

    create_latencies: list[float] = []
    for index in range(task_count):
        started = time.perf_counter()
        repository.create_task(
            task_id=f"bench-{index:06d}",
            idempotency_key=f"bench-key-{index:06d}",
            payload=payload,
        )
        create_latencies.append(time.perf_counter() - started)

    claim_latencies: list[float] = []
    claimed = 0
    while True:
        started = time.perf_counter()
        record = repository.claim_next_task()
        claim_latencies.append(time.perf_counter() - started)
        if record is None:
            break
        claimed += 1

    return {
        "task_count": task_count,
        "claimed_count": claimed,
        "database_size_bytes": database.stat().st_size,
        "create": _summary(create_latencies),
        "claim": _summary(claim_latencies[:-1]),
        "boundary": "single-process SQLite WAL; not a distributed throughput claim",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the local PaperAgent task repository")
    parser.add_argument("--tasks", type=int, default=500)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.database is None:
        with tempfile.TemporaryDirectory(prefix="paperagent-benchmark-") as directory:
            result = run_benchmark(Path(directory) / "benchmark.db", args.tasks)
    else:
        result = run_benchmark(args.database, args.tasks)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
