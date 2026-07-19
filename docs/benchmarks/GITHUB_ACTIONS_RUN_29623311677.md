# GitHub Actions SQLite Baseline — Run 29623311677

## Evidence identity

```text
Workflow:       PaperAgent Interview Evidence
Run:            29623311677
Head SHA:       62e649ff84da77e5c2546ce914c759565819c864
Runner:         GitHub-hosted Ubuntu 24.04
Python:         3.12
Task count:     500
Artifact:       paperagent-interview-evidence
Artifact ID:    8422947228
Artifact digest sha256:0caf737dd9ca7fc70dd3f057a5a908808c5b754264086977befff8e8ef5badcf
```

The evidence job also built and installed the PaperAgent wheel in a fresh virtual environment,
installed the independent external-plugin example, invoked it through the installed CLI, ran the
credential-free interview demo, and exported the OpenAPI document.

## Measured result

| Operation | p50 | p95 | Maximum |
|---|---:|---:|---:|
| Transactional task create | 0.838 ms | 2.230 ms | 392.450 ms |
| Transactional task claim | 0.847 ms | 6.335 ms | 100.234 ms |

Additional observations:

```text
Created tasks:       500
Uniquely claimed:    500
Database file size:  471,040 bytes
Boundary:            single-process SQLite WAL
```

## Interpretation

The median result shows that local durable task bookkeeping is small compared with literature and LLM
latency. The maximum and p95 values must not be presented as dedicated-hardware capacity numbers. This
job ran on shared CI infrastructure and also performed package building and installation, so occasional
scheduler and filesystem pauses are expected.

This benchmark proves only that:

- all 500 tasks were transactionally created;
- all 500 tasks were claimed once;
- the benchmark output contract is reproducible;
- the current implementation runs within the documented local single-process boundary.

It does not prove:

- distributed-worker throughput;
- public-service capacity;
- multi-tenant isolation;
- remote provider latency;
- a production service-level objective.

Use the script in `scripts/repository_benchmark.py` to compare commits on the same runner class. A move
to PostgreSQL or a distributed queue should be driven by measured lock waiting and product requirements,
not by extrapolating this one run.
