"""Re8.2 WP1 — deterministic Tailor Gate cycle and pass reuse.

The legacy reflection gate runner derives ``round_idx`` from the total length of
``reflection_gate_results[gate_name]``. That is correct for one evaluation
cycle, but final-review repair can route through Tailor again after Tailor has
already passed. Re-entering the legacy runner then consumes another round and
may eventually emit a cap result even though Tailor's semantic inputs did not
change.

This module wraps only ``tailor_gate_node``. It leaves the existing evaluator,
schema, prompts, cap, and routing functions untouched while separating:

* canonical dependency fingerprints;
* bounded evaluation cycles;
* auditable reuse events that never consume evaluation rounds.

Re8.2 post-merge review additionally guarantees that legacy ``skip``/``reuse``
log entries never consume a real evaluation round and that only the active,
latest evaluated pass can be reused.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from . import reflection_gates as _legacy
from ._util import emit_trace as _emit

_GATE = _legacy.GATE_TAILOR
_FINGERPRINT_VERSION = "re8.2-tailor-gate-fingerprint/v2"
_NON_EVALUATION_GENERATORS = {"skip", "reuse"}

# Keys explicitly excluded from dependency fingerprints. They are either
# sensitive, non-serializable, local-machine-specific, or operational noise.
_EXCLUDED_KEYS = {
    "raw_input",
    "pdf_bytes",
    "pdf_path",
    "local_pdf_path",
    "local_path",
    "trace_events",
    "reasoning_ledger",
    "timestamp",
    "created_at",
    "updated_at",
    "elapsed",
    "elapsed_ms",
    "provider_request_id",
    "request_id",
    "generated_by",
}

_SEED_IDENTITY_FIELDS = (
    "seed_id",
    "resolved_title",
    "title",
    "authors",
    "year",
    "doi",
    "arxiv_id",
    "canonical_url",
    "existence_status",
    "role",
    "fulltext_status",
)


def _json_safe(value: Any) -> Any:
    """Return a deterministic, JSON-serializable representation."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        items = sorted(value.items(), key=lambda pair: str(pair[0]))
        for raw_key, item in items:
            key = str(raw_key)
            if key in _EXCLUDED_KEYS:
                continue
            safe = _json_safe(item)
            if safe is not None or item is None:
                out[key] = safe
        return out
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_json_safe(item) for item in value]
        return sorted(items, key=_canonical_json)
    return {"type": type(value).__name__}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sort_records(records: Any, keys: tuple[str, ...]) -> list[Any]:
    safe_records = _json_safe(records if isinstance(records, list) else [])
    if not isinstance(safe_records, list):
        return []

    def sort_key(item: Any) -> tuple[str, ...]:
        if not isinstance(item, dict):
            return ("", _canonical_json(item))
        primary = tuple(str(item.get(key, "")) for key in keys)
        return (*primary, _canonical_json(item))

    return sorted(safe_records, key=sort_key)


def _project_tailored_method(raw: Any) -> dict[str, Any]:
    tailored = _json_safe(raw if isinstance(raw, dict) else {})
    if not isinstance(tailored, dict):
        return {}

    if "candidate_modules" in tailored:
        tailored["candidate_modules"] = _sort_records(
            tailored.get("candidate_modules"),
            ("module_id", "name", "source_evidence_id", "source"),
        )
    if "compatibility_analysis" in tailored:
        tailored["compatibility_analysis"] = _sort_records(
            tailored.get("compatibility_analysis"),
            ("module_id", "name", "source_evidence_id"),
        )
    if "ablation_matrix" in tailored:
        tailored["ablation_matrix"] = _sort_records(
            tailored.get("ablation_matrix"), ("experiment_id", "name", "variant")
        )
    if "evidence_gaps_for_research" in tailored:
        tailored["evidence_gaps_for_research"] = _sort_records(
            tailored.get("evidence_gaps_for_research"),
            ("gap_id", "priority", "description"),
        )

    for field in (
        "fair_comparison_requirements",
        "limitations",
        "validation_warnings",
    ):
        if field in tailored:
            tailored[field] = _sort_records(tailored.get(field), ())

    assembly = tailored.get("assembly_plan")
    if isinstance(assembly, dict):
        assembly = dict(assembly)
        if "modules" in assembly:
            assembly["modules"] = _sort_records(
                assembly.get("modules"), ("module_id", "name", "source")
            )
        if "connections" in assembly:
            assembly["connections"] = _sort_records(
                assembly.get("connections"),
                ("from", "source", "to", "target", "integration_point"),
            )
        if "expected_interfaces" in assembly:
            assembly["expected_interfaces"] = _sort_records(
                assembly.get("expected_interfaces"), ("name", "from", "to")
            )
        tailored["assembly_plan"] = assembly
    return tailored


def _project_evidence_gaps(raw: Any) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        gap = {
            "gap_id": item.get("gap_id"),
            "lane_id": item.get("lane_id"),
            "question": item.get("question"),
            "status": item.get("status"),
            "evidence_delta": _json_safe(item.get("evidence_delta")),
            "evidence_ids": sorted(str(x) for x in (item.get("evidence_ids") or [])),
        }
        gaps.append(gap)
    return sorted(gaps, key=lambda x: (str(x.get("gap_id", "")), _canonical_json(x)))


def _project_seed_identity(raw: Any) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        seed = {field: _json_safe(item.get(field)) for field in _SEED_IDENTITY_FIELDS}
        seeds.append(seed)
    return sorted(
        seeds,
        key=lambda x: (
            str(x.get("seed_id", "")),
            str(x.get("doi", "")),
            str(x.get("arxiv_id", "")),
            str(x.get("resolved_title") or x.get("title") or ""),
            _canonical_json(x),
        ),
    )


def tailor_gate_input_projection(state: ResearchState) -> dict[str, Any]:
    """Project only stable semantic dependencies of the Tailor Gate."""
    tailored = _project_tailored_method(state.get("tailored_method"))
    ablation = tailored.get("ablation_matrix")
    if not ablation:
        ablation = _sort_records(state.get("ablation_matrix"), ("experiment_id", "name"))
    return {
        "schema": _FINGERPRINT_VERSION,
        "tailored_method": tailored,
        "evidence_gaps": _project_evidence_gaps(state.get("evidence_gaps")),
        "seed_identity": _project_seed_identity(state.get("seed_cards")),
        "ablation_matrix": ablation or [],
    }


def tailor_gate_input_fingerprint(state: ResearchState) -> str:
    payload = _canonical_json(tailor_gate_input_projection(state))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _as_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _counts_as_evaluation_result(entry: Any) -> bool:
    """Return whether a historical result consumes an evaluation round."""
    return (
        isinstance(entry, dict)
        and str(entry.get("generated_by") or "").lower()
        not in _NON_EVALUATION_GENERATORS
    )


def _latest_evaluation(log: list[dict[str, Any]]) -> tuple[int, dict[str, Any]] | None:
    for index in range(len(log) - 1, -1, -1):
        entry = log[index]
        if _counts_as_evaluation_result(entry):
            return index, entry
    return None


def _can_reuse_previous_pass(
    state: ResearchState,
    previous: Any,
    fingerprint: str,
    full_log: list[dict[str, Any]],
) -> bool:
    """Allow reuse only for the active cycle's latest evaluated pass.

    Fingerprint equality alone is insufficient: an older pass can be followed by
    a later revise/unresolved cycle. Reusing that stale pass would leave routing
    and fused-verdict consumers reading the later failure from the evaluation
    log. Active cycle metadata plus the latest evaluated result keep those views
    consistent without appending a synthetic pass.
    """
    if not isinstance(previous, dict):
        return False
    if previous.get("verdict") != "pass":
        return False
    if previous.get("generated_by") in _NON_EVALUATION_GENERATORS:
        return False
    if previous.get("input_fingerprint") != fingerprint:
        return False

    active_fingerprint = (state.get("gate_input_fingerprint") or {}).get(_GATE)
    if active_fingerprint != fingerprint:
        return False

    active_cycle = _as_non_negative_int((state.get("gate_cycle_id") or {}).get(_GATE))
    if _as_non_negative_int(previous.get("cycle_id")) != active_cycle:
        return False

    latest = _latest_evaluation(full_log)
    if latest is None:
        return False
    latest_index, latest_result = latest
    if latest_result.get("verdict") != "pass":
        return False
    if _as_non_negative_int(latest_result.get("round_idx")) != _as_non_negative_int(
        previous.get("evaluation_round_idx")
    ):
        return False

    stored_index = previous.get("result_log_index")
    if stored_index is not None and _as_non_negative_int(stored_index) != latest_index:
        return False
    return True


def _reuse_previous_pass(
    state: ResearchState,
    previous: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    t0 = time.time()
    cycle_id = _as_non_negative_int(previous.get("cycle_id"))
    source_round = _as_non_negative_int(previous.get("evaluation_round_idx"))
    source_log_index = _as_non_negative_int(previous.get("result_log_index"))
    counts = dict(state.get("gate_reuse_count") or {})
    reuse_count = _as_non_negative_int(counts.get(_GATE)) + 1
    counts[_GATE] = reuse_count

    reuse_event = {
        "gate_name": _GATE,
        "event_type": "gate_pass_reused",
        "reused_previous_pass": True,
        "source_cycle_id": cycle_id,
        "source_round_idx": source_round,
        "source_result_log_index": source_log_index,
        "input_fingerprint": fingerprint,
        "generated_by": "reuse",
        "reuse_count": reuse_count,
    }
    trace = _emit(
        f"reflection_gate::{_GATE}",
        t0,
        {
            "activated": True,
            "cycle_id": cycle_id,
            "evaluation_round_idx": source_round,
            "reused_previous_pass": True,
        },
        {
            "verdict": "pass",
            "generated_by": "reuse",
            "input_fingerprint": fingerprint,
            "reuse_count": reuse_count,
        },
        [],
        "reuse",
        [],
        state_keys=[
            "last_gate_pass",
            "gate_reuse_count",
            "gate_reuse_events",
            "reasoning_ledger",
            "trace_events",
        ],
    )
    ledger_result = {
        "verdict": "pass",
        "round_idx": source_round,
        "re_search_requests": [],
        "unresolved_gaps": [],
        "rationale": previous.get("rationale", "reused previous Tailor Gate pass"),
        "generated_by": "reuse",
    }
    ledger = _legacy._make_gate_ledger(
        gate_name=_GATE,
        decision_id=f"{_GATE}-reuse-c{cycle_id}-n{reuse_count}",
        result=ledger_result,
    )
    return {
        "gate_reuse_count": counts,
        "gate_reuse_events": [reuse_event],
        "reasoning_ledger": [ledger],
        "trace_events": [trace],
    }


def tailor_gate_node(state: ResearchState) -> dict[str, Any]:
    """Run, reuse, or start a new bounded Tailor Gate evaluation cycle."""
    fingerprint = tailor_gate_input_fingerprint(state)
    full_results = dict(state.get("reflection_gate_results") or {})
    full_log = list(full_results.get(_GATE, []))
    last_passes = dict(state.get("last_gate_pass") or {})
    previous = last_passes.get(_GATE)

    if _can_reuse_previous_pass(state, previous, fingerprint, full_log):
        return _reuse_previous_pass(state, previous, fingerprint)

    active_fingerprints = dict(state.get("gate_input_fingerprint") or {})
    cycle_ids = dict(state.get("gate_cycle_id") or {})
    cycle_starts = dict(state.get("gate_cycle_start_index") or {})

    active_fingerprint = active_fingerprints.get(_GATE)
    cycle_id = _as_non_negative_int(cycle_ids.get(_GATE))
    start_index = _as_non_negative_int(cycle_starts.get(_GATE))
    if start_index > len(full_log):
        start_index = 0

    if active_fingerprint is None:
        # Legacy skip-only histories must not consume real evaluation rounds.
        # If real evaluations exist, preserve all of them conservatively so a
        # legacy checkpoint cannot bypass an already-consumed cap.
        evaluation_indices = [
            i for i, entry in enumerate(full_log) if _counts_as_evaluation_result(entry)
        ]
        start_index = evaluation_indices[0] if evaluation_indices else len(full_log)
    elif active_fingerprint != fingerprint:
        cycle_id += 1
        start_index = len(full_log)

    cycle_history = full_log[start_index:]
    current_cycle_before = [
        entry for entry in cycle_history if _counts_as_evaluation_result(entry)
    ]
    delegated_state = dict(state)
    delegated_results = dict(full_results)
    delegated_results[_GATE] = current_cycle_before
    delegated_state["reflection_gate_results"] = delegated_results

    patch = dict(_legacy.tailor_gate_node(delegated_state))
    delegated_after = dict(patch.get("reflection_gate_results") or delegated_results)
    current_cycle_after = list(delegated_after.get(_GATE, current_cycle_before))
    appended_results = current_cycle_after[len(current_cycle_before):]

    merged_results = dict(delegated_after)
    merged_results[_GATE] = full_log + appended_results
    patch["reflection_gate_results"] = merged_results

    active_fingerprints[_GATE] = fingerprint
    cycle_ids[_GATE] = cycle_id
    cycle_starts[_GATE] = start_index
    patch["gate_input_fingerprint"] = active_fingerprints
    patch["gate_cycle_id"] = cycle_ids
    patch["gate_cycle_start_index"] = cycle_starts

    last_result = appended_results[-1] if appended_results else (
        current_cycle_after[-1] if current_cycle_after else {}
    )
    evaluation_round_idx = _as_non_negative_int(
        last_result.get("round_idx"), len(current_cycle_before)
    )
    result_log_index = len(merged_results[_GATE]) - 1
    evaluation_event = {
        "gate_name": _GATE,
        "event_type": "gate_evaluated",
        "cycle_id": cycle_id,
        "evaluation_round_idx": evaluation_round_idx,
        "input_fingerprint": fingerprint,
        "verdict": last_result.get("verdict", "unresolved"),
        "generated_by": last_result.get("generated_by", "unknown"),
        "result_log_index": result_log_index,
    }
    patch["gate_evaluation_events"] = list(patch.get("gate_evaluation_events") or []) + [
        evaluation_event
    ]

    cycle_trace = _emit(
        f"reflection_gate_cycle::{_GATE}",
        time.time(),
        {
            "cycle_id": cycle_id,
            "evaluation_round_idx": evaluation_round_idx,
            "cycle_start_index": start_index,
        },
        {
            "verdict": evaluation_event["verdict"],
            "generated_by": evaluation_event["generated_by"],
            "input_fingerprint": fingerprint,
        },
        [],
        str(evaluation_event["generated_by"]),
        [],
        state_keys=[
            "reflection_gate_results",
            "gate_cycle_id",
            "gate_input_fingerprint",
            "gate_evaluation_events",
            "trace_events",
        ],
    )
    patch["trace_events"] = list(patch.get("trace_events") or []) + [cycle_trace]

    if last_result.get("verdict") == "pass":
        last_passes[_GATE] = {
            "verdict": "pass",
            "evaluation_round_idx": evaluation_round_idx,
            "cycle_id": cycle_id,
            "input_fingerprint": fingerprint,
            "generated_by": last_result.get("generated_by", "unknown"),
            "rationale": last_result.get("rationale", ""),
            "result_log_index": result_log_index,
        }
        patch["last_gate_pass"] = last_passes
    elif _GATE in last_passes:
        # The cached pass is no longer current. A tombstone overwrites the
        # nested merge-dict entry without pretending an old pass is active.
        last_passes[_GATE] = {}
        patch["last_gate_pass"] = last_passes

    return patch


__all__ = [
    "tailor_gate_input_projection",
    "tailor_gate_input_fingerprint",
    "tailor_gate_node",
]
