# Failure Model

PaperAgent treats failure handling as part of the product contract rather than an implementation detail.

## Failure classes

| Failure | Retry | Repair | Terminal behavior |
|---|---:|---:|---|
| Authentication / permission | No | No | Fail closed |
| Invalid provider request | No | No | Fail closed |
| Unsupported structured-output capability | No | No | Fail closed |
| HTTP 429 | Bounded | No | Retry within budget, otherwise fail |
| Provider 5xx | Bounded | No | Retry within budget, otherwise fail |
| Timeout / transport interruption | Bounded | No | Retry within budget, otherwise fail |
| Invalid JSON or schema mismatch | No transport retry | At most once | Accept repaired valid output or fail |
| Call/token/time/cost budget exhaustion | No | No | Fail closed |
| Unknown usage with configured cost ceiling | No | No | Fail closed because cost cannot be proven |
| Retrieval evidence unavailable | Bounded by workflow policy | No | Produce blocked/insufficient-evidence state or fail |
| User cancellation | No | No | Cancel at the next workflow boundary |
| Process restart during execution | No automatic replay | No | Mark failed with `PROCESS_RESTARTED` |
| Plugin load ambiguity | No | No | Reject all ambiguous candidates |
| Plugin exception | No | No | Convert to typed invocation failure |

## Retry versus repair

A retry repeats the same logical call after a transient transport or provider failure. A repair is a new structured-output request whose only purpose is to transform an invalid response into the required schema.

They are accounted separately because repair consumes an additional model call and can hide model-quality defects if left unbounded.

## Error observability

Persisted telemetry may include:

- task, call, attempt, and request identifiers;
- provider and model name;
- latency;
- retry and repair counts;
- token usage and estimated cost when available;
- typed failure category;
- hashes or fingerprints.

It must not include API credentials, authorization headers, raw chain-of-thought, or unrestricted prompt/response bodies.

## Residual risks

- A remote call may complete after local timeout or cancellation and still be billed.
- Provider usage reporting may be delayed or absent.
- An explicitly authorized external Python plugin executes in-process and is not sandboxed.
- SQLite WAL improves local concurrency but does not turn the process into a distributed queue.
- Deterministic offline tests do not prove live model quality or scientific validity.
