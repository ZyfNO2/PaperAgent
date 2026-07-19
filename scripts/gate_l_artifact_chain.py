"""Verify immutable artifact links across the formal Gate L workflow chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_relative(raw: str) -> Path:
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or path.as_posix() in {"", "."}:
        raise ValueError(f"unsafe checksum path: {raw!r}")
    return Path(path.as_posix())


def verify_sha256sums(
    directory: Path, *, filename: str = "SHA256SUMS"
) -> dict[str, str]:
    sums_path = directory / filename
    if not sums_path.is_file():
        raise ValueError(f"missing checksum inventory: {sums_path}")
    observed: dict[str, str] = {}
    for line_number, raw in enumerate(
        sums_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not _HEX64_RE.fullmatch(parts[0]):
            raise ValueError(f"{sums_path}:{line_number} has invalid checksum syntax")
        relative = _safe_relative(parts[1].lstrip("*"))
        key = relative.as_posix()
        if key in observed:
            raise ValueError(f"duplicate checksum entry: {key}")
        target = directory / relative
        if not target.is_file():
            raise ValueError(f"checksum target is missing: {target}")
        actual = _sha256(target)
        if actual != parts[0]:
            raise ValueError(f"checksum mismatch for {key}: {actual} != {parts[0]}")
        observed[key] = actual
    if not observed:
        raise ValueError("checksum inventory must not be empty")
    return observed


def verify_freeze_bundle(
    bundle_dir: Path,
    *,
    expected_source_sha: str,
    expected_run_id: str,
) -> dict[str, Any]:
    if not _SHA_RE.fullmatch(expected_source_sha):
        raise ValueError("expected_source_sha must be a full lowercase commit SHA")
    checksums = verify_sha256sums(bundle_dir)
    for required in ("manifest.json", "freeze-record.json", "gate-l-formal-freeze.tgz"):
        if required not in checksums:
            raise ValueError(f"freeze checksum inventory is missing {required}")
    manifest_path = bundle_dir / "manifest.json"
    record_path = bundle_dir / "freeze-record.json"
    manifest = _read_json(manifest_path)
    record = _read_json(record_path)
    if manifest.get("formal_contract_version") != "gate-l.formal.v1":
        raise ValueError("unexpected formal contract version")
    if manifest.get("contract_version") != "gate-l.acceptance.v3":
        raise ValueError("unexpected acceptance contract version")
    if manifest.get("status") != "frozen_pending_execution":
        raise ValueError("freeze manifest must be frozen_pending_execution")
    if manifest.get("scientific_behavior_cutoff_sha") != expected_source_sha:
        raise ValueError("freeze manifest source SHA mismatch")
    if record.get("source_sha") != expected_source_sha:
        raise ValueError("freeze record source SHA mismatch")
    if str(record.get("github_run_id")) != str(expected_run_id):
        raise ValueError("freeze record workflow run mismatch")
    if record.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("freeze record manifest digest mismatch")
    return {
        "record_type": "verified_formal_freeze",
        "source_sha": expected_source_sha,
        "freeze_run_id": str(expected_run_id),
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "case_file_sha256": manifest.get("case_file_sha256"),
        "artifact_bundle_sha256": manifest.get("frozen_artifact_bundle_sha256"),
        "checksums": checksums,
    }


def _manifest_case_ids(manifest: dict[str, Any], repo_root: Path) -> set[str]:
    raw = manifest.get("case_file")
    if not isinstance(raw, str) or not raw:
        raise ValueError("manifest case_file is required")
    case_path = repo_root / _safe_relative(raw)
    if not case_path.is_file():
        raise ValueError(f"manifest case file is missing: {case_path}")
    case_ids: set[str] = set()
    for line_number, raw_line in enumerate(
        case_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        item = json.loads(raw_line)
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError(f"{case_path}:{line_number} has invalid case data")
        case_id = item["case_id"]
        if case_id in case_ids:
            raise ValueError(f"duplicate case ID in frozen holdout: {case_id}")
        case_ids.add(case_id)
    if len(case_ids) != 16:
        raise ValueError(f"formal holdout must contain 16 cases, found {len(case_ids)}")
    return case_ids


def verify_execution_bundle(
    bundle_dir: Path,
    *,
    manifest_path: Path,
    expected_source_sha: str,
    repo_root: Path = Path("."),
) -> dict[str, Any]:
    if not _SHA_RE.fullmatch(expected_source_sha):
        raise ValueError("expected_source_sha must be a full lowercase commit SHA")
    checksums = verify_sha256sums(bundle_dir)
    required_files = {"run-record.json", "formal-preflight.json"}
    if not required_files <= set(checksums):
        missing = sorted(required_files - set(checksums))
        raise ValueError(
            f"execution checksum inventory is missing: {', '.join(missing)}"
        )
    manifest = _read_json(manifest_path)
    run_record_path = bundle_dir / "run-record.json"
    preflight_path = bundle_dir / "formal-preflight.json"
    run_record = _read_json(run_record_path)
    preflight = _read_json(preflight_path)
    manifest_digest = _sha256(manifest_path)
    if manifest.get("scientific_behavior_cutoff_sha") != expected_source_sha:
        raise ValueError("execution source SHA does not match frozen manifest")
    if run_record.get("formal_run") is not True:
        raise ValueError("execution bundle is not a formal full-corpus run")
    if run_record.get("case_count") != 16:
        raise ValueError("formal execution must contain exactly 16 cases")
    if run_record.get("selected_case_ids") not in ([], None):
        raise ValueError("formal execution must not contain a case filter")
    identity = run_record.get("execution_identity")
    if not isinstance(identity, dict):
        raise ValueError("run record execution_identity is required")
    if identity.get("repo_sha") != expected_source_sha:
        raise ValueError("run record source SHA mismatch")
    if identity.get("manifest_sha256") != manifest_digest:
        raise ValueError("run record manifest digest mismatch")
    if preflight.get("runtime_sha") != expected_source_sha:
        raise ValueError("formal preflight source SHA mismatch")
    if preflight.get("manifest_sha256") != manifest_digest:
        raise ValueError("formal preflight manifest digest mismatch")
    formal_contract = run_record.get("formal_contract")
    if not isinstance(formal_contract, dict):
        raise ValueError("run record formal_contract is required")
    if formal_contract.get("preflight_sha256") != _sha256(preflight_path):
        raise ValueError("run record preflight digest mismatch")
    if formal_contract.get("artifact_bundle_sha256") != manifest.get(
        "frozen_artifact_bundle_sha256"
    ):
        raise ValueError("run record frozen artifact bundle mismatch")

    case_ids = _manifest_case_ids(manifest, repo_root)
    entries = run_record.get("cases")
    if not isinstance(entries, list):
        raise ValueError("run record cases must be a list")
    run_ids = {
        item.get("case_id")
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    if run_ids != case_ids or len(entries) != len(case_ids):
        raise ValueError("run record does not cover the exact frozen case set")
    evidence_dir = bundle_dir / "per-case"
    evidence_paths = {path.stem: path for path in evidence_dir.glob("*.json")}
    if set(evidence_paths) != case_ids:
        raise ValueError("per-case evidence does not cover the exact frozen case set")
    expected_checksum_paths = {f"per-case/{case_id}.json" for case_id in case_ids}
    missing_evidence_checksums = sorted(expected_checksum_paths - set(checksums))
    if missing_evidence_checksums:
        raise ValueError(
            "execution checksum inventory is missing per-case evidence: "
            + ", ".join(missing_evidence_checksums)
        )
    for case_id, evidence_path in evidence_paths.items():
        evidence = _read_json(evidence_path)
        if evidence.get("case_id") != case_id:
            raise ValueError(f"evidence case ID mismatch: {evidence_path}")
        if evidence.get("execution_identity") != identity:
            raise ValueError(f"evidence execution identity mismatch: {case_id}")
        for payload_field, digest_field in (
            ("output_payload", "output_digest"),
            ("trace_payload", "trace_digest"),
        ):
            if payload_field not in evidence:
                raise ValueError(f"{case_id}: {payload_field} is required")
            value = evidence.get(digest_field)
            if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
                raise ValueError(f"{case_id}: {digest_field} must be a SHA-256 digest")
            if _canonical_digest(evidence[payload_field]) != value:
                raise ValueError(
                    f"{case_id}: {digest_field} does not match {payload_field}"
                )
    return {
        "record_type": "verified_formal_execution",
        "source_sha": expected_source_sha,
        "manifest_sha256": manifest_digest,
        "run_record_sha256": _sha256(run_record_path),
        "formal_preflight_sha256": _sha256(preflight_path),
        "formal_execution_eligible": run_record.get("formal_execution_eligible")
        is True,
        "case_count": len(case_ids),
        "checksums": checksums,
    }


def _write_result(result: dict[str, Any], output: Path | None) -> None:
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(payload, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify formal Gate L artifact-chain links"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    sums = commands.add_parser("verify-sums")
    sums.add_argument("--bundle-dir", type=Path, required=True)
    sums.add_argument("--output", type=Path)
    freeze = commands.add_parser("verify-freeze")
    freeze.add_argument("--bundle-dir", type=Path, required=True)
    freeze.add_argument("--source-sha", required=True)
    freeze.add_argument("--run-id", required=True)
    freeze.add_argument("--output", type=Path)
    execution = commands.add_parser("verify-execution")
    execution.add_argument("--bundle-dir", type=Path, required=True)
    execution.add_argument("--manifest", type=Path, required=True)
    execution.add_argument("--source-sha", required=True)
    execution.add_argument("--repo-root", type=Path, default=Path("."))
    execution.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "verify-sums":
            result = {
                "record_type": "verified_checksum_inventory",
                "checksums": verify_sha256sums(args.bundle_dir),
            }
        elif args.command == "verify-freeze":
            result = verify_freeze_bundle(
                args.bundle_dir,
                expected_source_sha=args.source_sha,
                expected_run_id=args.run_id,
            )
        else:
            result = verify_execution_bundle(
                args.bundle_dir,
                manifest_path=args.manifest,
                expected_source_sha=args.source_sha,
                repo_root=args.repo_root,
            )
        _write_result(result, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L artifact-chain error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
