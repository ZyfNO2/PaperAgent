from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from paperagent.schemas.trace import TraceEvent
from paperagent.trace_replay import (
    TraceFixtureManifest,
    TraceMutationCase,
    apply_trace_mutation,
    build_trace_replay_report,
    canonical_trace_payload,
    trace_digest,
)

FIXTURE_DIR = Path("evals/cloud_trace/steel-defect-pollution-001")
_TRACE_LIST = TypeAdapter(list[TraceEvent])
_CASE_LIST = TypeAdapter(list[TraceMutationCase])


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture() -> tuple[
    TraceFixtureManifest, list[TraceEvent], list[TraceMutationCase]
]:
    manifest = TraceFixtureManifest.model_validate(
        _load_json(FIXTURE_DIR / "manifest.json")
    )
    events = _TRACE_LIST.validate_python(_load_json(FIXTURE_DIR / "trace.json"))
    cases = _CASE_LIST.validate_python(_load_json(FIXTURE_DIR / "cases.json"))
    return manifest, events, cases


def test_canonical_trace_digest_is_stable_and_manifest_bound() -> None:
    manifest, events, _ = _load_fixture()

    assert canonical_trace_payload(events) == canonical_trace_payload(list(events))
    assert trace_digest(events) == trace_digest(list(events))
    assert trace_digest(events) == manifest.expected_trace_digest


def test_mutation_corpus_contains_at_least_ten_negative_cases() -> None:
    _, _, cases = _load_fixture()

    assert sum(1 for case in cases if not case.expected_pass) >= 10
    assert cases[0].mutation == "none"
    assert cases[0].expected_pass is True


def test_every_trace_mutation_is_classified_as_expected() -> None:
    manifest, baseline, cases = _load_fixture()

    for case in cases:
        events = apply_trace_mutation(baseline, case.mutation)
        report = build_trace_replay_report(
            case_id=case.case_id,
            fixture_version=manifest.fixture_version,
            source_commit="test-source-sha",
            events=events,
            expected_event_count=case.expected_event_count
            or manifest.expected_event_count,
            expected_route_sequence=(
                case.expected_route_sequence
                if case.expected_route_sequence is not None
                else manifest.expected_route_sequence
            ),
            expected_trace_digest=case.expected_trace_digest
            or manifest.expected_trace_digest,
        )

        assert report.passed is case.expected_pass, case.case_id
        assert set(case.required_error_codes).issubset(report.error_codes), case.case_id


def test_replay_report_hashes_optional_artifacts() -> None:
    manifest, events, _ = _load_fixture()

    report = build_trace_replay_report(
        case_id="artifact-digest-case",
        fixture_version=manifest.fixture_version,
        source_commit="test-source-sha",
        events=events,
        expected_event_count=manifest.expected_event_count,
        expected_route_sequence=manifest.expected_route_sequence,
        expected_trace_digest=manifest.expected_trace_digest,
        final_state={"execution": {"status": "completed"}},
        report={"status": "completed", "evidence_ids": ["ev-1"]},
        verdict="REVISE",
        blocker="BASELINE_NOT_REPRODUCED",
    )

    assert report.passed is True
    assert report.final_state_digest is not None
    assert report.report_digest is not None
    assert report.verdict == "REVISE"
    assert report.blocker == "BASELINE_NOT_REPRODUCED"
