"""Formal factory for PaperClaw academic adapters with version and dependency checks."""

from __future__ import annotations

from pathlib import Path

from paperagent.academic.paperclaw_adapter import (
    PaperClawAcademicArtifactSink,
    PaperClawAcademicEvidenceSource,
)

_SUPPORTED_SCHEMA_VERSION = "academic.v1"


class PaperClawDependencyError(RuntimeError):
    pass


class PaperClawVersionError(RuntimeError):
    pass


def _check_paperclaw_available() -> None:
    try:
        from importlib import import_module

        import_module("paperclaw.academic")
    except ImportError as exc:
        raise PaperClawDependencyError(
            "PaperClaw academic module is not installed. "
            "Install with: pip install paperclaw[academic] "
            "(requires Python 3.12+ and PyMuPDF)"
        ) from exc


def _check_schema_version() -> None:
    from importlib import import_module

    academic = import_module("paperclaw.academic")
    version = getattr(academic, "ACADEMIC_SCHEMA_VERSION", None)
    if version is None:
        raise PaperClawVersionError(
            "PaperClaw academic module does not expose ACADEMIC_SCHEMA_VERSION; "
            f"expected {_SUPPORTED_SCHEMA_VERSION}. Upgrade paperclaw."
        )
    if version != _SUPPORTED_SCHEMA_VERSION:
        raise PaperClawVersionError(
            f"PaperClaw academic schema version {version} is incompatible; "
            f"PaperAgent requires {_SUPPORTED_SCHEMA_VERSION}."
        )


def _check_capabilities(academic: object, *names: str) -> None:
    missing = [name for name in names if not hasattr(academic, name)]
    if missing:
        raise PaperClawVersionError(
            "PaperClaw academic capabilities are incompatible; missing: "
            + ", ".join(sorted(missing))
        )


def create_paperclaw_evidence_source(
    workspace: str | Path,
    project_id: str,
) -> PaperClawAcademicEvidenceSource:
    _check_paperclaw_available()
    _check_schema_version()
    from importlib import import_module

    academic = import_module("paperclaw.academic")
    _check_capabilities(academic, "AcademicRuntime", "EvidenceBundle", "EvidenceLocator")
    runtime = academic.AcademicRuntime.for_workspace(workspace, project_id)
    return PaperClawAcademicEvidenceSource(runtime)


def create_paperclaw_artifact_sink(
    workspace: str | Path,
) -> PaperClawAcademicArtifactSink:
    _check_paperclaw_available()
    _check_schema_version()
    from importlib import import_module

    artifacts = import_module("paperclaw.artifacts")
    store = artifacts.FileArtifactStore(Path(workspace) / ".paperclaw" / "artifacts")
    return PaperClawAcademicArtifactSink(store)
