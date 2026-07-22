from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paperagent.eval_runtime_reporting import canonical_sha256, validate_public_dataset_digest

MANIFEST_SCHEMA = "paperagent.eval-run.manifest.v2"
REQUIRED_RUN_FILES = (
    "states.jsonl",
    "run-traces.jsonl",
    "execution-summary.json",
    "prompt-log.jsonl",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_commit(value: str, *, name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a full 40-character Git commit SHA")
    return normalized


def _parse_timestamp(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"execution summary must contain {name}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def _derive_run_status(summary: dict[str, Any]) -> str:
    selected = int(summary.get("selected_case_count", 0))
    attempted = len(summary.get("attempted_case_ids", []))
    completed = int(summary.get("completed", 0))
    runtime_errors = int(summary.get("runtime_errors", len(summary.get("errors", []))))
    if selected > 0 and attempted == selected and completed == selected and runtime_errors == 0:
        return "completed"
    return "partial"


def build_snapshot(
    *,
    run_id: str,
    run_dir: Path,
    public_dataset_path: Path,
    authoring_dataset_path: Path,
    diagnostic_report_path: Path,
    output_root: Path,
    run_source_commit: str,
    snapshot_commit: str,
    source_branch: str,
    scorer_version: str,
    replace: bool = False,
) -> Path:
    if not run_id or run_id.endswith(("-partial", "-completed")):
        raise ValueError("run_id must be a base ID without a status suffix")
    run_source_commit = _require_commit(run_source_commit, name="run_source_commit")
    snapshot_commit = _require_commit(snapshot_commit, name="snapshot_commit")

    for name in REQUIRED_RUN_FILES:
        if not (run_dir / name).is_file():
            raise ValueError(f"run directory is missing required file: {name}")
    if not diagnostic_report_path.is_file():
        raise ValueError("diagnostic report is missing")

    public_dataset = _load_json(public_dataset_path)
    public_sha256 = validate_public_dataset_digest(public_dataset)
    generated_from = public_dataset.get("generated_from")
    if not isinstance(generated_from, dict):
        raise ValueError("public dataset is missing generated_from provenance")
    authoring_commit = _require_commit(
        str(generated_from.get("authoring_commit") or ""),
        name="public generated_from.authoring_commit",
    )

    authoring_dataset = _load_json(authoring_dataset_path)
    authoring_sha256 = canonical_sha256(authoring_dataset)
    if generated_from.get("authoring_sha256") != authoring_sha256:
        raise ValueError("public dataset authoring_sha256 does not match authoring dataset")

    summary = _load_json(run_dir / "execution-summary.json")
    if summary.get("public_dataset_sha256") != public_sha256:
        raise ValueError("execution summary public_dataset_sha256 does not match public dataset")
    if summary.get("source_sha") != run_source_commit:
        raise ValueError("execution summary source_sha does not match run_source_commit")

    started_at = _parse_timestamp(summary.get("started_at"), name="started_at")
    completed_at = _parse_timestamp(summary.get("completed_at"), name="completed_at")
    if completed_at <= started_at:
        raise ValueError("completed_at must be later than started_at")
    duration_seconds = summary.get("duration_seconds")
    if not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0:
        raise ValueError("execution summary duration_seconds must be positive")
    measured = (completed_at - started_at).total_seconds()
    if abs(float(duration_seconds) - measured) > max(1.0, measured * 0.01):
        raise ValueError("duration_seconds is inconsistent with started_at/completed_at")

    run_status = _derive_run_status(summary)
    output_dir = output_root / f"{run_id}-{run_status}"
    if output_dir.exists():
        if not replace:
            raise FileExistsError(output_dir)
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for name in REQUIRED_RUN_FILES:
        shutil.copy2(run_dir / name, output_dir / name)
    shutil.copy2(diagnostic_report_path, output_dir / "diagnostic-report.json")
    shutil.copy2(public_dataset_path, output_dir / "public-dataset.json")

    checksums = {
        path.name: _sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name not in {"manifest.json", "checksums.sha256"}
    }
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())),
        encoding="utf-8",
    )

    attempted = len(summary.get("attempted_case_ids", []))
    completed = int(summary.get("completed", 0))
    runtime_errors = int(summary.get("runtime_errors", len(summary.get("errors", []))))
    diagnostic = _load_json(output_dir / "diagnostic-report.json")
    scientific_acceptance = bool(
        run_status == "completed"
        and diagnostic.get("passed") is True
        and runtime_errors == 0
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "run_id": run_id,
        "artifact_directory": output_dir.name,
        "run_status": run_status,
        "scientific_acceptance": scientific_acceptance,
        "dataset_id": public_dataset.get("dataset_id"),
        "public_dataset_sha256": public_sha256,
        "authoring_dataset_sha256": authoring_sha256,
        "authoring_commit": authoring_commit,
        "run_source_commit": run_source_commit,
        "snapshot_commit": snapshot_commit,
        "source_branch": source_branch,
        "scorer_version": scorer_version,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": float(duration_seconds),
        "case_count": int(summary.get("selected_case_count", 0)),
        "attempted": attempted,
        "completed": completed,
        "runtime_errors": runtime_errors,
        "files": checksums,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--public-dataset", type=Path, required=True)
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--diagnostic-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-source-commit", required=True)
    parser.add_argument("--snapshot-commit", required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--scorer-version", required=True)
    parser.add_argument("--replace", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = build_snapshot(
        run_id=args.run_id,
        run_dir=args.run_dir,
        public_dataset_path=args.public_dataset,
        authoring_dataset_path=args.authoring,
        diagnostic_report_path=args.diagnostic_report,
        output_root=args.output_root,
        run_source_commit=args.run_source_commit,
        snapshot_commit=args.snapshot_commit,
        source_branch=args.source_branch,
        scorer_version=args.scorer_version,
        replace=args.replace,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
