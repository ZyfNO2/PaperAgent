"""Fail-closed generation context built only from accepted evidence."""

from __future__ import annotations

from dataclasses import dataclass

from paperagent.academic.contracts import (
    AcademicEvidenceLedger,
    AcademicEvidenceSource,
    EvidenceLocatorView,
)


class AcademicEvidenceInsufficientError(RuntimeError):
    """Generation must abstain when no accepted, resolvable evidence remains."""


@dataclass(frozen=True)
class AcceptedContextEntry:
    evidence_id: str
    locator: EvidenceLocatorView
    text: str
    provenance: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class AcademicContextManifest:
    entries: tuple[AcceptedContextEntry, ...]
    evidence_ids: tuple[str, ...]
    character_budget: int
    token_budget: int
    characters_used: int
    retrieval_trace_ids: tuple[str, ...]


def build_accepted_context_manifest(
    ledger: AcademicEvidenceLedger,
    source: AcademicEvidenceSource,
    *,
    character_budget: int,
    token_budget: int,
    retrieval_trace_ids: tuple[str, ...],
) -> AcademicContextManifest:
    if character_budget < 1 or token_budget < 1:
        raise ValueError("context budgets must be positive")
    accepted = [entry for entry in ledger.entries if entry.status == "accepted"]
    resolved_entries: list[AcceptedContextEntry] = []
    remaining = character_budget
    for entry in accepted:
        try:
            candidate = source.resolve(entry.locator)
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            raise AcademicEvidenceInsufficientError(
                f"accepted evidence {entry.evidence_id} is not resolvable"
            ) from exc
        if candidate.locator != entry.locator:
            raise AcademicEvidenceInsufficientError(
                f"accepted evidence {entry.evidence_id} locator identity drifted"
            )
        if candidate.evidence_id != entry.evidence_id:
            raise AcademicEvidenceInsufficientError(
                f"accepted evidence {entry.evidence_id} source identity drifted"
            )
        text = candidate.text[:remaining]
        if text:
            resolved_entries.append(
                AcceptedContextEntry(
                    entry.evidence_id,
                    entry.locator,
                    text,
                    candidate.provenance,
                    entry.limitations,
                )
            )
            remaining -= len(text)
        if remaining == 0:
            break
    if not resolved_entries:
        raise AcademicEvidenceInsufficientError(
            "no accepted evidence is available; abstain with REVISE/NO-GO"
        )
    return AcademicContextManifest(
        tuple(resolved_entries),
        tuple(item.evidence_id for item in resolved_entries),
        character_budget,
        token_budget,
        character_budget - remaining,
        retrieval_trace_ids,
    )
