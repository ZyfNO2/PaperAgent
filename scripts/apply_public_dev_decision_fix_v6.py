from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "src/paperagent/academic_methodology.py",
    """def _verified_evidence(item: EvidenceItem | None) -> bool:
    return (
        item is not None
        and item.verified
        and _present(item.stable_identifier)
        and _present(item.content_hash)
        and bool(item.supported_claims)
    )


def _module_contract_complete(module: ModuleCard) -> bool:
""",
    """def _verified_evidence(item: EvidenceItem | None) -> bool:
    return (
        item is not None
        and item.verified
        and _present(item.stable_identifier)
        and _present(item.content_hash)
        and bool(item.supported_claims)
    )


def _provenance_failure_severity(item: EvidenceItem | None) -> AuditSeverity:
    identity_valid = (
        item is not None
        and item.verified
        and _present(item.stable_identifier)
        and _present(item.content_hash)
    )
    return AuditSeverity.ERROR if identity_valid else AuditSeverity.CRITICAL


def _module_contract_complete(module: ModuleCard) -> bool:
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """            _verified_evidence(baseline_evidence),
            AuditSeverity.ERROR,
            (
                "baseline provenance references verified evidence with a stable "
""",
    """            _verified_evidence(baseline_evidence),
            _provenance_failure_severity(baseline_evidence),
            (
                "baseline provenance references verified evidence with a stable "
""",
)
replace_once(
    "src/paperagent/academic_methodology.py",
    """                _verified_evidence(module_evidence),
                AuditSeverity.ERROR,
                (
                    f"module {module.name} references verified provenance with a "
""",
    """                _verified_evidence(module_evidence),
                _provenance_failure_severity(module_evidence),
                (
                    f"module {module.name} references verified provenance with a "
""",
)

print("dynamic provenance severity patch applied")
