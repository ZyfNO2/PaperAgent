"""Claim generation and citation/claim mismatch checking."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from paperagent.academic.contracts import (
    AcademicEvidenceLedger,
    AcademicEvidenceSource,
    AcademicLocator,
)

_NUMERIC_CLAIM = re.compile(
    r"(?:\d+\.?\d*\s*%|\d+\.?\d*\s*(?:px|mm|dB|ms|fps)"
    r"|outperform|surpass|achieve|improve|reduce|increase"
    r"|优于|超过|提升|降低|达到)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GeneratedClaim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]
    locator_bindings: tuple[AcademicLocator, ...]
    confidence: str = "medium"
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class MismatchReport:
    claim_id: str
    evidence_id: str
    kind: str
    detail: str


def generate_claims_from_ledger(
    ledger: AcademicEvidenceLedger,
    source: AcademicEvidenceSource,
    *,
    question: str,
) -> tuple[GeneratedClaim, ...]:
    accepted = [e for e in ledger.entries if e.status == "accepted"]
    if not accepted:
        return ()
    claims: list[GeneratedClaim] = []
    for entry in accepted:
        try:
            candidate = source.resolve(entry.locator)
        except (KeyError, OSError, RuntimeError, ValueError):
            continue
        if candidate.evidence_id != entry.evidence_id or candidate.locator != entry.locator:
            continue
        claim_text = _extract_claim_sentence(candidate.text, question)
        claims.append(
            GeneratedClaim(
                claim_id=(
                    "claim-"
                    + hashlib.sha256(f"{entry.evidence_id}\0{claim_text}".encode()).hexdigest()[:12]
                ),
                text=claim_text,
                evidence_ids=(entry.evidence_id,),
                locator_bindings=(entry.locator,) if entry.locator else (),
                confidence="high",
                limitations=entry.limitations or (),
            )
        )
    return tuple(claims)


def _extract_claim_sentence(evidence_text: str, question: str) -> str:
    sentences = re.split(
        r"(?<!\d)[.!?](?!\d)|[\u3002\uFF01\uFF1F\n]",
        evidence_text,
    )
    for sentence in sentences:
        if _NUMERIC_CLAIM.search(sentence) and len(sentence.strip()) > 20:
            return sentence.strip()
    if sentences and sentences[0].strip():
        return sentences[0].strip()
    return f"Evidence supports: {question[:100]}"


def check_citation_claim_mismatch(
    claims: tuple[GeneratedClaim, ...],
    source: AcademicEvidenceSource,
) -> tuple[MismatchReport, ...]:
    mismatches: list[MismatchReport] = []
    for claim in claims:
        for locator in claim.locator_bindings:
            try:
                resolved = source.resolve(locator)
            except (KeyError, OSError, RuntimeError, ValueError):
                mismatches.append(
                    MismatchReport(
                        claim_id=claim.claim_id,
                        evidence_id=claim.evidence_ids[0] if claim.evidence_ids else "",
                        kind="locator_unresolvable",
                        detail=f"locator {locator.object_id} could not be resolved",
                    )
                )
                continue
            if resolved.locator.object_id != locator.object_id:
                mismatches.append(
                    MismatchReport(
                        claim_id=claim.claim_id,
                        evidence_id=claim.evidence_ids[0] if claim.evidence_ids else "",
                        kind="locator_identity_mismatch",
                        detail=(
                            f"resolved object_id {resolved.locator.object_id} "
                            f"!= claimed {locator.object_id}"
                        ),
                    )
                )
            if resolved.locator.source_hash != locator.source_hash:
                mismatches.append(
                    MismatchReport(
                        claim_id=claim.claim_id,
                        evidence_id=claim.evidence_ids[0] if claim.evidence_ids else "",
                        kind="source_hash_mismatch",
                        detail=(
                            f"resolved source_hash {resolved.locator.source_hash[:16]}... "
                            f"!= claimed {locator.source_hash[:16]}..."
                        ),
                    )
                )
            evidence_text = _normalize_text(resolved.text)
            claim_text = _normalize_text(claim.text)
            if claim_text and claim_text not in evidence_text:
                mismatches.append(
                    MismatchReport(
                        claim_id=claim.claim_id,
                        evidence_id=(claim.evidence_ids[0] if claim.evidence_ids else ""),
                        kind="semantic_support_mismatch",
                        detail="claim text is not present in the bound evidence scope",
                    )
                )
            claim_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", claim.text))
            evidence_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", resolved.text))
            if not claim_numbers <= evidence_numbers:
                mismatches.append(
                    MismatchReport(
                        claim_id=claim.claim_id,
                        evidence_id=(claim.evidence_ids[0] if claim.evidence_ids else ""),
                        kind="numeric_value_mismatch",
                        detail="claim contains numeric values absent from evidence",
                    )
                )
    return tuple(mismatches)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())
