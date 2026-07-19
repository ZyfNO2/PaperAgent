# Repository Benchmark Baseline

## Purpose

The benchmark establishes a reproducible local baseline for the current SQLite task repository. It is not a production capacity claim and should not be compared across machines without recording the environment.

## Run

```bash
python scripts/repository_benchmark.py \
  --tasks 500 \
  --output build/repository-benchmark.json
```

The benchmark measures:

- per-task transactional create latency;
- per-task transactional claim latency;
- claimed task uniqueness;
- resulting database file size.

The concurrency test suite separately verifies:

- concurrent submission of one Idempotency-Key creates one durable task;
- concurrent claims do not return the same task twice.

## Required reporting fields

```text
commit SHA
Python version
operating system
CPU / runner class
task count
database location and filesystem
create p50 / p95 / max
claim p50 / p95 / max
database size
failures
```

## Interpretation

The benchmark is useful for regression detection inside the same environment. It does not model:

- remote model latency;
- literature-provider latency;
- multiple processes or hosts;
- network storage;
- multi-tenant workloads;
- long-running review and export traffic.

## Scaling decision

A move to PostgreSQL and a distributed worker system should be evaluated when measured lock waiting, write latency, worker utilization, or operational requirements exceed the accepted local single-process boundary. The decision should use service-level objectives rather than an arbitrary task-count threshold.
