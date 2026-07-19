from __future__ import annotations

from collections import defaultdict
from typing import Any

from paperagent.academic_methodology import EvidenceItem as MethodEvidenceItem
from paperagent.schemas import EvidenceBundle, EvidenceSynthesis, MethodProposal

_ALLOWED_EVIDENCE_METADATA = frozenset(
    {
        "doi",
        "arxiv_id",
        "openalex_id",
        "semantic_scholar_id",
        "license",
        "repository_ref",
        "verification_status",
        "providers",
        "baseline_reproduced",
        "baseline_reproduced_metric",
        "baseline_compute_fit",
        "baseline_parity_verified",
        "dataset_fingerprint",
        "environment_fingerprint",
    }
)


def accepted_evidence_ledger(evidence: EvidenceBundle) -> list[dict[str, Any]]:
    """Return server-owned accepted evidence fields safe for method design."""

    return [
        {
            "evidence_id": item.evidence_id,
            "source_type": item.source_type,
            "title": item.title,
            "stable_identifier": item.stable_identifier,
            "summary": item.summary,
            "content_hash": item.content_hash,
            "provider": item.provider,
            "metadata": {
                key: value
                for key, value in item.metadata.items()
                if key in _ALLOWED_EVIDENCE_METADATA and value
            },
        }
        for item in evidence.accepted_items()
    ]


def _claims_by_evidence(synthesis: EvidenceSynthesis) -> dict[str, tuple[str, ...]]:
    claims: dict[str, list[str]] = defaultdict(list)
    for claim in synthesis.verified_findings:
        for evidence_id in claim.evidence_ids:
            if claim.text not in claims[evidence_id]:
                claims[evidence_id].append(claim.text)
    return {evidence_id: tuple(values) for evidence_id, values in claims.items()}


def _limitations_by_evidence(synthesis: EvidenceSynthesis) -> dict[str, tuple[str, ...]]:
    limitations: dict[str, list[str]] = defaultdict(list)
    for assessment in synthesis.gap_assessments:
        for evidence_id in assessment.evidence_ids:
            for limitation in assessment.limitations:
                if limitation not in limitations[evidence_id]:
                    limitations[evidence_id].append(limitation)
    for conflict in synthesis.conflicts:
        for evidence_id in conflict.evidence_ids:
            if conflict.summary not in limitations[evidence_id]:
                limitations[evidence_id].append(conflict.summary)
    return {evidence_id: tuple(values) for evidence_id, values in limitations.items()}


def _metadata_value(metadata: dict[str, str], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _metadata_bool(metadata: dict[str, str], key: str) -> bool | None:
    value = _metadata_value(metadata, key)
    if value is None:
        return None
    normalized = value.lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean metadata {key}: {value!r}")


def bind_method_evidence(
    method: MethodProposal,
    evidence: EvidenceBundle,
    synthesis: EvidenceSynthesis,
) -> MethodProposal:
    """Replace model-authored provenance with server-owned evidence fields.

    The model may choose accepted evidence IDs, but it cannot author verification,
    identifiers, hashes, licenses, repository references, or supported claims.
    """

    accepted = {item.evidence_id: item for item in evidence.accepted_items()}
    claims = _claims_by_evidence(synthesis)
    limitations = _limitations_by_evidence(synthesis)
    canonical_ids = {item.evidence_id for item in method.methodology_plan.evidence}
    unknown = canonical_ids - set(accepted)
    if unknown:
        raise ValueError(f"canonical method evidence is not accepted: {sorted(unknown)}")

    bound_evidence: list[MethodEvidenceItem] = []
    for declared in method.methodology_plan.evidence:
        source = accepted[declared.evidence_id]
        repository_ref = _metadata_value(source.metadata, "repository_ref")
        if repository_ref is None and source.source_type == "repository":
            repository_ref = source.locator
        bound_evidence.append(
            MethodEvidenceItem(
                evidence_id=source.evidence_id,
                source_type=source.source_type,
                title=source.title,
                stable_identifier=source.stable_identifier,
                verified=True,
                supported_claims=claims.get(source.evidence_id, ()),
                limitations=limitations.get(source.evidence_id, ()),
                content_hash=source.content_hash,
                license=_metadata_value(source.metadata, "license"),
                repository_ref=repository_ref,
            )
        )

    evidence_by_id = {item.evidence_id: item for item in bound_evidence}
    baseline = method.methodology_plan.baseline
    baseline_evidence = evidence_by_id.get(baseline.source_evidence_id or "")
    baseline_metadata = (
        accepted[baseline.source_evidence_id].metadata
        if baseline.source_evidence_id in accepted
        else {}
    )
    bound_baseline = baseline.model_copy(
        update={
            "license": baseline_evidence.license if baseline_evidence is not None else None,
            "reproduced": _metadata_bool(baseline_metadata, "baseline_reproduced") is True,
            "reproduced_metric": _metadata_value(baseline_metadata, "baseline_reproduced_metric"),
            "compute_fit": _metadata_bool(baseline_metadata, "baseline_compute_fit"),
            "baseline_parity_verified": _metadata_bool(
                baseline_metadata, "baseline_parity_verified"
            ),
            "dataset_fingerprint": _metadata_value(baseline_metadata, "dataset_fingerprint"),
            "environment_fingerprint": _metadata_value(
                baseline_metadata, "environment_fingerprint"
            ),
        }
    )
    bound_modules = tuple(
        module.model_copy(
            update={
                "license": (
                    evidence_by_id[module.evidence_id].license
                    if module.evidence_id in evidence_by_id
                    else None
                )
            }
        )
        for module in method.methodology_plan.modules
    )
    bound_plan = method.methodology_plan.model_copy(
        update={
            "baseline": bound_baseline,
            "modules": bound_modules,
            "evidence": tuple(bound_evidence),
        }
    )
    payload = method.model_dump(mode="json")
    payload["methodology_plan"] = bound_plan.model_dump(mode="json")
    return MethodProposal.model_validate(payload)


__all__ = ["accepted_evidence_ledger", "bind_method_evidence"]
