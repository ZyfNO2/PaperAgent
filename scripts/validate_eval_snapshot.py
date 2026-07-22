from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paperagent.eval_runtime_reporting import canonical_sha256, validate_public_dataset_digest

MANIFEST_SCHEMA = "paperagent.eval-run.manifest.v2"
REQUIRED_FILES = {
    "states.jsonl",
    "run-traces.jsonl",
    "execution-summary.json",
    "prompt-log.jsonl",
    "diagnostic-report.json",
    "public-dataset.json",
}


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


def _require_hex(value: object, *, name: str, length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip().lower()
    if len(normalized) != length or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be {length} lowercase hexadecimal characters")
    return normalized


def _timestamp(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def validate_snapshot(*, snapshot_dir: Path, authoring_path: Path) -> dict[str, Any]:
    manifest = _load_json(snapshot_dir / "manifest.json")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected snapshot manifest schema")

    run_id = str(manifest.get("run_id") or "")
    run_status = str(manifest.get("run_status") or "")
    if run_status not in {"completed", "partial"}:
        raise ValueError("run_status must be completed or partial")
    expected_directory = f"{run_id}-{run_status}"
    if (
        snapshot_dir.name != expected_directory
        or manifest.get("artifact_directory") != expected_directory
    ):
        raise ValueError("snapshot directory name does not match run_id and run_status")

    public_sha256 = _require_hex(
        manifest.get("public_dataset_sha256"),
        name="public_dataset_sha256",
        length=64,
    )
    authoring_sha256 = _require_hex(
        manifest.get("authoring_dataset_sha256"),
        name="authoring_dataset_sha256",
        length=64,
    )
    _require_hex(manifest.get("run_source_commit"), name="run_source_commit", length=40)
    _require_hex(manifest.get("snapshot_commit"), name="snapshot_commit", length=40)
    _require_hex(manifest.get("authoring_commit"), name="authoring_commit", length=40)

    started_at = _timestamp(manifest.get("started_at"), name="started_at")
    completed_at = _timestamp(manifest.get("completed_at"), name="completed_at")
    if completed_at <= started_at:
        raise ValueError("completed_at must be later than started_at")
    duration = manifest.get("duration_seconds")
    if not isinstance(duration, int | float) or duration <= 0:
        raise ValueError("duration_seconds must be positive")
    measured = (completed_at - started_at).total_seconds()
    if abs(float(duration) - measured) > max(1.0, measured * 0.01):
        raise ValueError("duration_seconds is inconsistent with timestamps")

    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files must be an object")
    missing = REQUIRED_FILES - set(files)
    if missing:
        raise ValueError(f"manifest is missing required checksums: {sorted(missing)}")
    for name, expected_digest in files.items():
        _require_hex(expected_digest, name=f"files[{name!r}]", length=64)
        path = snapshot_dir / name
        if not path.is_file():
            raise ValueError(f"snapshot file is missing: {name}")
        actual = _sha256_file(path)
        if actual != expected_digest:
            raise ValueError(f"checksum mismatch for {name}")

    checksum_lines = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (snapshot_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
        if "  " in line
    }
    if checksum_lines != files:
        raise ValueError("checksums.sha256 does not match manifest files")

    public_dataset = _load_json(snapshot_dir / "public-dataset.json")
    if validate_public_dataset_digest(public_dataset) != public_sha256:
        raise ValueError("public dataset digest does not match manifest")
    generated_from = public_dataset.get("generated_from")
    if not isinstance(generated_from, dict):
        raise ValueError("public dataset is missing generated_from provenance")
    if generated_from.get("authoring_sha256") != authoring_sha256:
        raise ValueError("public dataset authoring digest does not match manifest")
    if generated_from.get("authoring_commit") != manifest.get("authoring_commit"):
        raise ValueError("public dataset authoring commit does not match manifest")

    authoring = _load_json(authoring_path)
    if canonical_sha256(authoring) != authoring_sha256:
        raise ValueError("authoring dataset digest does not match manifest")

    summary = _load_json(snapshot_dir / "execution-summary.json")
    if summary.get("public_dataset_sha256") != public_sha256:
        raise ValueError("execution summary public dataset digest does not match manifest")
    if summary.get("source_sha") != manifest.get("run_source_commit"):
        raise ValueError("execution summary source SHA does not match manifest")

    selected = int(summary.get("selected_case_count", 0))
    attempted = len(summary.get("attempted_case_ids", []))
    completed = int(summary.get("completed", 0))
    runtime_errors = int(summary.get("runtime_errors", len(summary.get("errors", []))))
    if manifest.get("case_count") != selected:
        raise ValueError("manifest case_count does not match execution summary")
    if manifest.get("attempted") != attempted:
        raise ValueError("manifest attempted count does not match execution summary")
    if manifest.get("completed") != completed:
        raise ValueError("manifest completed count does not match execution summary")
    if manifest.get("runtime_errors") != runtime_errors:
        raise ValueError("manifest runtime_errors does not match execution summary")

    if run_status == "completed" and (
        selected <= 0 or attempted != selected or completed != selected or runtime_errors != 0
    ):
        raise ValueError("completed snapshot contains incomplete cases or runtime errors")
    if (
        run_status == "partial"
        and attempted == selected
        and completed == selected
        and runtime_errors == 0
    ):
        raise ValueError("partial snapshot has complete runtime evidence")
    if manifest.get("scientific_acceptance") is True and run_status != "completed":
        raise ValueError("partial snapshot cannot claim scientific acceptance")

    return {
        "schema": "paperagent.eval-run.snapshot-validation.v1",
        "snapshot": str(snapshot_dir),
        "run_id": run_id,
        "run_status": run_status,
        "validated_files": len(files),
        "public_dataset_sha256": public_sha256,
        "authoring_dataset_sha256": authoring_sha256,
        "passed": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path)
    parser.add_argument("--authoring", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = validate_snapshot(snapshot_dir=args.snapshot_dir, authoring_path=args.authoring)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
