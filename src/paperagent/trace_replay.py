from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.outcome import TraceAuditResult, TraceInvariantResult
from paperagent.schemas.trace import TraceEvent
from paperagent.telemetry.hashing import hash_payload

TraceMutationKind = Literal[
    "none",
    "duplicate_event",
    "mixed_run_id",
    "missing_route",
    "failed_without_error_code",
    "failed_status_mismatch",
    "completed_status_mismatch",
    "orphan_parent_span",
    "append_after_terminal",
    "reorder_events",
]


class TraceFixtureManifest(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    case_id: str = Field(min_length=1)
    fixture_version: str = Field(min_length=1)
    category: str = Field(min_length=1)
    expected_event_count: int = Field(ge=1)
    expected_route_sequence: list[str] = Field(default_factory=list)
    expected_trace_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class TraceMutationCase(FrozenModel):
    case_id: str = Field(min_length=1)
    mutation: TraceMutationKind
    expected_pass: bool
    expected_event_count: int | None = Field(default=None, ge=1)
    expected_route_sequence: list[str] | None = None
    expected_trace_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    required_error_codes: list[str] = Field(default_factory=list)


class TraceReplayReport(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    case_id: str
    fixture_version: str
    source_commit: str
    trace_digest: str
    final_state_digest: str | None = None
    report_digest: str | None = None
    event_count: int = Field(ge=0)
    route_sequence: list[str]
    verdict: str | None = None
    blocker: str | None = None
    invariant_results: list[TraceInvariantResult]
    passed: bool
    error_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report(self) -> TraceReplayReport:
        derived_errors = [item.invariant_id for item in self.invariant_results if not item.passed]
        if self.passed != (not derived_errors):
            raise ValueError("replay passed flag must be derived from invariant results")
        if self.error_codes != derived_errors:
            raise ValueError("replay error_codes must match failed invariant order")
        return self


def canonical_trace_payload(events: Sequence[TraceEvent]) -> list[dict[str, Any]]:
    """Return the strict, sequence-numbered representation used for replay digests."""

    return [
        {
            "sequence_number": index,
            **event.model_dump(mode="json", exclude_none=True),
        }
        for index, event in enumerate(events, start=1)
    ]


def trace_digest(events: Sequence[TraceEvent]) -> str:
    return hash_payload(canonical_trace_payload(events))


def _route_sequence(events: Sequence[TraceEvent]) -> list[str]:
    return [
        event.route
        for event in events
        if event.event_type == "route.decided" and event.route is not None
    ]


def audit_trace_events(
    events: Sequence[TraceEvent],
    *,
    expected_event_count: int | None = None,
    expected_route_sequence: Sequence[str] | None = None,
    expected_trace_digest: str | None = None,
) -> TraceAuditResult:
    results: list[TraceInvariantResult] = []

    def record(invariant_id: str, passed: bool, details: str | None = None) -> None:
        results.append(
            TraceInvariantResult(
                invariant_id=invariant_id,
                passed=passed,
                details=details,
            )
        )

    record("TRACE_NONEMPTY", bool(events), "a replay trace must contain at least one event")

    run_ids = {event.run_id for event in events}
    record(
        "TRACE_SINGLE_RUN_ID",
        len(run_ids) <= 1,
        f"run_ids={sorted(run_ids)}" if len(run_ids) > 1 else None,
    )

    event_ids = [event.event_id for event in events]
    duplicate_event_ids = sorted(
        event_id for event_id, count in Counter(event_ids).items() if count > 1
    )
    record(
        "TRACE_EVENT_IDS_UNIQUE",
        not duplicate_event_ids,
        f"duplicate_event_ids={duplicate_event_ids}" if duplicate_event_ids else None,
    )

    span_ids = [event.span_id for event in events]
    duplicate_span_ids = sorted(
        span_id for span_id, count in Counter(span_ids).items() if count > 1
    )
    record(
        "TRACE_SPAN_IDS_UNIQUE",
        not duplicate_span_ids,
        f"duplicate_span_ids={duplicate_span_ids}" if duplicate_span_ids else None,
    )

    span_id_set = set(span_ids)
    orphan_parents = sorted(
        {
            event.parent_span_id
            for event in events
            if event.parent_span_id is not None and event.parent_span_id not in span_id_set
        }
    )
    record(
        "TRACE_PARENT_SPANS_EXIST",
        not orphan_parents,
        f"orphan_parent_span_ids={orphan_parents}" if orphan_parents else None,
    )

    failure_errors: list[str] = []
    status_errors: list[str] = []
    route_errors: list[str] = []
    lifecycle_errors: list[str] = []
    active_nodes: defaultdict[str, int] = defaultdict(int)

    for index, event in enumerate(events, start=1):
        if event.status == "failed" and not event.error_code:
            failure_errors.append(f"event {index} failed without error_code")
        if event.event_type.endswith(".failed") and event.status != "failed":
            status_errors.append(
                f"event {index} type={event.event_type} uses status={event.status}"
            )
        if event.event_type.endswith((".completed", ".responded")) and event.status != "completed":
            status_errors.append(
                f"event {index} type={event.event_type} uses status={event.status}"
            )
        if event.event_type.endswith((".started", ".requested")) and event.status != "started":
            status_errors.append(
                f"event {index} type={event.event_type} uses status={event.status}"
            )
        if event.event_type == "route.decided" and (event.status != "decided" or not event.route):
            route_errors.append(
                f"event {index} route.decided requires status=decided and a non-empty route"
            )

        if event.event_type == "node.started":
            active_nodes[event.node] += 1
        elif event.event_type in {"node.completed", "node.failed"}:
            if active_nodes[event.node] <= 0:
                lifecycle_errors.append(
                    f"event {index} closes node={event.node} without a preceding node.started"
                )
            else:
                active_nodes[event.node] -= 1

    unclosed_nodes = sorted(node for node, count in active_nodes.items() if count != 0)
    if unclosed_nodes:
        lifecycle_errors.append(f"unclosed_nodes={unclosed_nodes}")

    record(
        "TRACE_FAILED_EVENTS_HAVE_ERROR_CODES",
        not failure_errors,
        "; ".join(failure_errors) if failure_errors else None,
    )
    record(
        "TRACE_EVENT_STATUS_MATCHES_TYPE",
        not status_errors,
        "; ".join(status_errors) if status_errors else None,
    )
    record(
        "TRACE_ROUTE_EVENTS_COMPLETE",
        not route_errors,
        "; ".join(route_errors) if route_errors else None,
    )
    record(
        "TRACE_NODE_LIFECYCLE_ORDERED",
        not lifecycle_errors,
        "; ".join(lifecycle_errors) if lifecycle_errors else None,
    )

    terminal_indexes = [
        index
        for index, event in enumerate(events)
        if event.node == "persist_node" and event.event_type in {"node.completed", "node.failed"}
    ]
    terminal_is_final = not terminal_indexes or (
        len(terminal_indexes) == 1 and terminal_indexes[0] == len(events) - 1
    )
    record(
        "TRACE_TERMINAL_EVENT_IS_FINAL",
        terminal_is_final,
        f"terminal_indexes={terminal_indexes}, event_count={len(events)}"
        if not terminal_is_final
        else None,
    )

    if expected_event_count is not None:
        record(
            "TRACE_EVENT_COUNT_MATCHES_MANIFEST",
            len(events) == expected_event_count,
            f"actual={len(events)}, expected={expected_event_count}",
        )

    routes = _route_sequence(events)
    if expected_route_sequence is not None:
        expected_routes = list(expected_route_sequence)
        record(
            "TRACE_ROUTE_SEQUENCE_MATCHES_MANIFEST",
            routes == expected_routes,
            f"actual={routes}, expected={expected_routes}",
        )

    digest = trace_digest(events)
    if expected_trace_digest is not None:
        record(
            "TRACE_DIGEST_MATCHES_MANIFEST",
            digest == expected_trace_digest,
            f"actual={digest}, expected={expected_trace_digest}",
        )

    error_codes = [result.invariant_id for result in results if not result.passed]
    return TraceAuditResult(
        passed=not error_codes,
        results=results,
        error_codes=error_codes,
    )


def build_trace_replay_report(
    *,
    case_id: str,
    fixture_version: str,
    source_commit: str,
    events: Sequence[TraceEvent],
    expected_event_count: int | None = None,
    expected_route_sequence: Sequence[str] | None = None,
    expected_trace_digest: str | None = None,
    final_state: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
    verdict: str | None = None,
    blocker: str | None = None,
) -> TraceReplayReport:
    audit = audit_trace_events(
        events,
        expected_event_count=expected_event_count,
        expected_route_sequence=expected_route_sequence,
        expected_trace_digest=expected_trace_digest,
    )
    return TraceReplayReport(
        case_id=case_id,
        fixture_version=fixture_version,
        source_commit=source_commit,
        trace_digest=trace_digest(events),
        final_state_digest=hash_payload(final_state) if final_state is not None else None,
        report_digest=hash_payload(report) if report is not None else None,
        event_count=len(events),
        route_sequence=_route_sequence(events),
        verdict=verdict,
        blocker=blocker,
        invariant_results=audit.results,
        passed=audit.passed,
        error_codes=audit.error_codes,
    )


def apply_trace_mutation(
    events: Sequence[TraceEvent],
    mutation: TraceMutationKind,
) -> list[TraceEvent]:
    mutated = list(events)
    if mutation == "none":
        return mutated
    if not mutated:
        raise ValueError("trace mutation requires at least one event")

    if mutation == "duplicate_event":
        mutated.insert(1, mutated[0])
    elif mutation == "mixed_run_id":
        mutated[1 if len(mutated) > 1 else 0] = mutated[1 if len(mutated) > 1 else 0].model_copy(
            update={"run_id": "run-mutated"}
        )
    elif mutation == "missing_route":
        index = next(
            index for index, event in enumerate(mutated) if event.event_type == "route.decided"
        )
        mutated[index] = mutated[index].model_copy(update={"route": None})
    elif mutation == "failed_without_error_code":
        mutated[0] = mutated[0].model_copy(
            update={"event_type": "node.failed", "status": "failed", "error_code": None}
        )
    elif mutation == "failed_status_mismatch":
        mutated[0] = mutated[0].model_copy(
            update={
                "event_type": "node.failed",
                "status": "completed",
                "error_code": "E_MUT",
            }
        )
    elif mutation == "completed_status_mismatch":
        mutated[1 if len(mutated) > 1 else 0] = mutated[1 if len(mutated) > 1 else 0].model_copy(
            update={"event_type": "node.completed", "status": "decided"}
        )
    elif mutation == "orphan_parent_span":
        mutated[0] = mutated[0].model_copy(update={"parent_span_id": "span-does-not-exist"})
    elif mutation == "append_after_terminal":
        terminal = mutated[-1]
        mutated.append(
            terminal.model_copy(
                update={
                    "event_id": "event-after-terminal",
                    "span_id": "span-after-terminal",
                    "node": "post_terminal_node",
                    "event_type": "node.started",
                    "status": "started",
                    "error_code": None,
                }
            )
        )
    elif mutation == "reorder_events":
        if len(mutated) < 2:
            raise ValueError("reorder_events requires at least two events")
        mutated[0], mutated[1] = mutated[1], mutated[0]
    else:  # pragma: no cover - Literal exhaustiveness guard
        raise ValueError(f"unsupported trace mutation: {mutation}")
    return mutated


__all__ = [
    "TraceFixtureManifest",
    "TraceMutationCase",
    "TraceMutationKind",
    "TraceReplayReport",
    "apply_trace_mutation",
    "audit_trace_events",
    "build_trace_replay_report",
    "canonical_trace_payload",
    "trace_digest",
]
