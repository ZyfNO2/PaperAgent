"""Fail-closed scientific acceptance scoring for Academic RAG P0.

This module scores recorded facts; it does not create questions, human gold,
scientific decisions, or reviewer approvals.  Missing denominators and missing
human/real-runtime gates remain blocked instead of being treated as zero.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

P0_PROTOCOL_VERSION = "academic-rag-p0-scientific-acceptance.v1"
P0_REPORT_SCHEMA = "academic-rag-p0-acceptance-report.v1"
ARTIFACT_TYPES = (
    "evidence_bundle",
    "paper_comparison",
    "baseline_card",
    "module_card",
    "compatibility_matrix",
    "experiment_matrix",
    "method_draft",
    "review_report",
)
Status = Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN"]


class P0AcceptanceError(ValueError):
    """Raised when an acceptance input cannot be safely scored."""


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: Status
    reason: str
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "reason": self.reason,
            "evidence_ref": self.evidence_ref,
        }


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_file_digest(path: Path, expected: str) -> str:
    """Verify a frozen resource before it can participate in scoring."""

    actual = canonical_sha256(path)
    if actual != expected:
        raise P0AcceptanceError(
            f"resource digest mismatch for {path}: expected {expected}, got {actual}"
        )
    return actual


def load_protocol(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P0AcceptanceError(f"cannot load P0 protocol: {path}") from exc
    if not isinstance(payload, dict):
        raise P0AcceptanceError("P0 protocol must be a JSON object")
    if payload.get("protocol_version") != P0_PROTOCOL_VERSION:
        raise P0AcceptanceError("unsupported P0 protocol version")
    return payload


def assert_protocol_compatible(protocols: Iterable[Mapping[str, object]]) -> None:
    """Reject mixed protocol or contract digests before scoring any result."""

    values = tuple(protocols)
    if not values:
        raise P0AcceptanceError("at least one protocol record is required")
    fields = ("protocol_version", "schema_digest", "golden_fixture_digest")
    for field in fields:
        observed = {record.get(field) for record in values}
        if len(observed) != 1:
            raise P0AcceptanceError(f"protocol {field} mismatch; scoring is blocked")
    if values[0].get("protocol_version") != P0_PROTOCOL_VERSION:
        raise P0AcceptanceError("unsupported P0 protocol version")


def validate_denominators(
    observed: Mapping[str, int],
    expected: Mapping[str, int],
) -> None:
    """Require an exact case denominator; changing it cannot hide failures."""

    if set(observed) != set(expected):
        raise P0AcceptanceError("denominator keys do not match the frozen protocol")
    for name, value in expected.items():
        actual = observed[name]
        if isinstance(actual, bool) or not isinstance(actual, int) or actual != value:
            raise P0AcceptanceError(f"denominator mismatch for {name}")


def score_accepted_context(
    context: Iterable[Mapping[str, object]],
) -> dict[str, int | None]:
    """Count rejected/conflicted evidence that leaked into generation context."""

    rows = tuple(context)
    violations = sum(row.get("status") != "accepted" for row in rows)
    rejected = sum(row.get("status") == "rejected" for row in rows)
    conflicted = sum(row.get("status") == "conflicted" for row in rows)
    return {
        "context_items": len(rows),
        "accepted_only_violation": violations,
        "rejected_leakage": rejected,
        "conflicted_leakage": conflicted,
    }


def score_claims(
    claims: Iterable[Mapping[str, object]],
    accepted_evidence_ids: Collection[str],
) -> dict[str, int | None]:
    """Classify unsupported claims and citation mismatches without judging prose."""

    rows = tuple(claims)
    unsupported = 0
    critical_unsupported = 0
    citation_mismatch = 0
    critical_citation_mismatch = 0
    for claim in rows:
        refs = claim.get("evidence_ids", ())
        evidence_ids = tuple(refs) if isinstance(refs, list | tuple | set) else ()
        is_unsupported = (
            claim.get("supported") is not True
            or not evidence_ids
            or any(str(ref) not in accepted_evidence_ids for ref in evidence_ids)
        )
        is_critical = claim.get("critical") is True or claim.get("severity") == "critical"
        if is_unsupported:
            unsupported += 1
            if is_critical:
                critical_unsupported += 1
        mismatch = claim.get("citation_match") is not True
        if mismatch:
            citation_mismatch += 1
            if is_critical:
                critical_citation_mismatch += 1
    return {
        "claim_count": len(rows),
        "unsupported_claim_count": unsupported,
        "critical_unsupported_claim_count": critical_unsupported,
        "citation_mismatch_count": citation_mismatch,
        "critical_citation_mismatch_count": critical_citation_mismatch,
    }


def score_artifacts(
    artifacts: Iterable[Mapping[str, object]],
    *,
    reviewer_approved: bool,
) -> dict[str, object]:
    """Score the eight Artifact contract projections and human review boundary."""

    rows = tuple(artifacts)
    by_type = {str(row.get("artifact_type")): row for row in rows}
    missing = [name for name in ARTIFACT_TYPES if name not in by_type]
    invalid = [
        name
        for name in ARTIFACT_TYPES
        if name in by_type
        and any(
            by_type[name].get(field) is not True
            for field in (
                "schema_valid",
                "required_fields_complete",
                "claim_evidence_coverage",
                "revision_traceable",
            )
        )
    ]
    return {
        "artifact_count": len(rows),
        "required_artifact_count": len(ARTIFACT_TYPES),
        "missing_artifacts": missing,
        "invalid_artifacts": invalid,
        "reviewer_approved": reviewer_approved,
        "status": "PASS" if not missing and not invalid and reviewer_approved else "BLOCKED",
    }


def decide_p0(
    proposed_decision: str,
    gate_statuses: Mapping[str, Status],
    *,
    critical_unsupported_claims: int | None,
    critical_citation_mismatches: int | None,
    false_go: int | None,
) -> dict[str, object]:
    """Return a conservative decision; no missing hard Gate can become GO."""

    required = tuple(gate_statuses.values())
    gates_complete = bool(required) and all(status == "PASS" for status in required)
    metrics_complete = all(
        value is not None
        for value in (
            critical_unsupported_claims,
            critical_citation_mismatches,
            false_go,
        )
    )
    hard_zero = metrics_complete and (
        critical_unsupported_claims == 0 and critical_citation_mismatches == 0 and false_go == 0
    )
    proposed_go = proposed_decision.strip().upper() == "GO"
    final_release = "GO" if gates_complete and hard_zero else "NO-GO"
    false_go_count = (
        1
        if proposed_go and final_release != "GO"
        else 0
        if false_go is not None
        else None
    )
    return {
        "overall_decision": "REVISE",
        "p0_release": final_release,
        "proposed_decision": proposed_decision,
        "false_go": false_go_count,
        "all_required_gates_pass": gates_complete,
        "critical_metrics_complete": metrics_complete,
    }


def build_blocked_report(protocol: Mapping[str, object]) -> dict[str, object]:
    """Create the honest pre-run report used by the operator pack."""

    assert_protocol_compatible((protocol,))
    question_pack = protocol.get("question_pack")
    question_pack_map = question_pack if isinstance(question_pack, Mapping) else {}
    gates = (
        GateResult("unit_automation", "NOT_RUN", "run the frozen test command"),
        GateResult("corpus_manifest", "PASS", "metadata/hash manifest is frozen"),
        GateResult(
            "real_papers",
            "BLOCKED",
            "controlled local real-paper files and license evidence are not supplied",
        ),
        GateResult(
            "questions_32",
            "BLOCKED",
            "32 IDs exist, but human question authoring is incomplete",
        ),
        GateResult("human_gold_labels", "BLOCKED", "human gold labels are absent"),
        GateResult("cross_paper_decisions", "BLOCKED", "two human scientific decisions are absent"),
        GateResult("real_minilm", "PASS", "recorded RTX 4070 SUPER MiniLM evidence is available"),
        GateResult("real_colqwen2", "BLOCKED", "fixed-revision ColQwen2 run did not complete"),
        GateResult("real_academic_llm", "BLOCKED", "no P0 academic workflow trace is supplied"),
        GateResult("native_windows", "BLOCKED", "manual Native Windows click-through is absent"),
        GateResult(
            "human_artifact_reviewer",
            "BLOCKED",
            "independent human Artifact review is absent",
        ),
    )
    decision = decide_p0(
        "REVISE",
        {gate.gate_id: gate.status for gate in gates},
        critical_unsupported_claims=None,
        critical_citation_mismatches=None,
        false_go=None,
    )
    return {
        "schema_version": P0_REPORT_SCHEMA,
        "protocol_version": protocol["protocol_version"],
        "starting_commit_pair": protocol.get("starting_commit_pair"),
        "schema_digest": protocol.get("schema_digest"),
        "golden_fixture_digest": protocol.get("golden_fixture_digest"),
        "resource_summary": {
            "real_paper_manifest_entries": protocol.get("corpus_manifest_entry_count"),
            "questions_expected": question_pack_map.get("count"),
            "question_pack_sha256": question_pack_map.get("sha256"),
            "artifact_manifest_sha256": question_pack_map.get("artifact_manifest_sha256"),
        },
        "gates": [gate.to_dict() for gate in gates],
        "evidence_classes": {
            "unit": "NOT_RUN",
            "fake_mock": "NOT_RUN",
            "generated_pdf": "NOT_RUN",
            "real_papers": "BLOCKED",
            "real_minilm": "PASS",
            "real_colqwen2": "BLOCKED",
            "real_academic_llm": "BLOCKED",
            "native_windows": "BLOCKED",
            "human_labels": "BLOCKED",
            "human_decisions": "BLOCKED",
            "human_artifact_review": "BLOCKED",
        },
        "metrics": {
            "critical_unsupported_claims": None,
            "critical_citation_mismatches": None,
            "false_go": None,
            "denominator_status": "BLOCKED",
        },
        **decision,
        "blockers": [gate.gate_id for gate in gates if gate.status == "BLOCKED"],
        "conclusion": "REVISE / P0 NO-GO",
    }


def render_report_markdown(report: Mapping[str, object]) -> str:
    gates = report.get("gates", ())
    lines = [
        "# P0 Scientific Acceptance Report",
        "",
        f"- Protocol: `{report.get('protocol_version')}`",
        f"- Overall decision: **{report.get('overall_decision')}**",
        f"- P0 Release: **{report.get('p0_release')}**",
        "",
        "## Gate status",
        "",
        "| Gate | Status | Reason |",
        "|---|---|---|",
    ]
    for gate in gates if isinstance(gates, list) else []:
        if isinstance(gate, dict):
            lines.append(
                f"| `{gate.get('gate_id')}` | `{gate.get('status')}` | {gate.get('reason')} |"
            )
    lines.extend(
        [
            "",
            "## Hard metrics",
            "",
            "Critical unsupported claims, critical citation mismatches, and false GO "
            "remain unscored (`BLOCKED`) until the frozen denominator and human/real "
            "evidence gates are complete.",
            "",
            "This report does not treat generated PDFs, Fake/Mock runs, automated "
            "labels, or LLM self-review as scientific acceptance evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "ARTIFACT_TYPES",
    "P0_PROTOCOL_VERSION",
    "P0_REPORT_SCHEMA",
    "P0AcceptanceError",
    "assert_protocol_compatible",
    "build_blocked_report",
    "canonical_sha256",
    "decide_p0",
    "load_protocol",
    "render_report_markdown",
    "score_accepted_context",
    "score_artifacts",
    "score_claims",
    "validate_denominators",
    "verify_file_digest",
]
