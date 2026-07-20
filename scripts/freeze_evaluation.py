from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_THRESHOLDS: dict[str, float | int] = {
    "decision_accuracy_minimum": 0.80,
    "hard_failure_count_maximum": 0,
    "fabricated_evidence_count_maximum": 0,
    "unsupported_comparator_count_maximum": 0,
    "adapter_created_pilot_count_maximum": 0,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_freeze_manifest(
    *,
    repository_root: Path,
    production_source_sha: str,
    benchmark_source_sha: str,
    production_digest: str,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    if not FULL_SHA.fullmatch(production_source_sha):
        raise ValueError("production_source_sha must be a full lowercase Git SHA")
    if not FULL_SHA.fullmatch(benchmark_source_sha):
        raise ValueError("benchmark_source_sha must be a full lowercase Git SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", production_digest):
        raise ValueError("production_digest must be a SHA-256 hex digest")

    root = repository_root.resolve()
    pinned_files = {
        "runner": root / "scripts/run_public_dev.py",
        "scorer": root / "scripts/score_runs.py",
        "production_scanner": root / "scripts/scan_production.py",
        "protocol": root / "docs/BENCHMARK_PROTOCOL.md",
        "case_schema": root / "schema/case.schema.json",
        "public_development_data": root / "data/public-dev-v2.jsonl",
    }
    missing = [name for name, path in pinned_files.items() if not path.is_file()]
    if missing:
        raise ValueError(f"freeze inputs missing: {missing}")

    effective_thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    manifest: dict[str, Any] = {
        "schema": "paperagent.academic-holdout.freeze.v2",
        "production_source_sha": production_source_sha,
        "benchmark_source_sha": benchmark_source_sha,
        "production_digest": production_digest,
        "file_sha256": {name: _sha256(path) for name, path in pinned_files.items()},
        "thresholds": effective_thresholds,
        "runtime_boundary": [
            "input.user_request",
            "input.supplied_materials[].title",
            "input.supplied_materials[].declared_role",
            "input.declared_constraints",
        ],
        "scorer_only_fields": [
            "case_id",
            "oracle",
            "metadata",
            "scoring_rules",
            "metamorphic_group",
        ],
        "public_development_status": "debuggable; not independent generalization evidence",
        "private_holdout_status": "not generated; author only after this manifest is frozen",
    }
    manifest["freeze_digest"] = hashlib.sha256(_canonical(manifest).encode("utf-8")).hexdigest()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze Academic Method Holdout v2 inputs.")
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--production-source-sha", required=True)
    parser.add_argument("--benchmark-source-sha", required=True)
    parser.add_argument("--production-scan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scan: Any = json.loads(args.production_scan.read_text(encoding="utf-8"))
    if not isinstance(scan, dict) or scan.get("passed") is not True:
        raise ValueError("production scan must exist and pass before freeze")
    production_digest = scan.get("production_digest")
    if not isinstance(production_digest, str):
        raise ValueError("production scan lacks production_digest")

    manifest = build_freeze_manifest(
        repository_root=args.repository_root,
        production_source_sha=args.production_source_sha,
        benchmark_source_sha=args.benchmark_source_sha,
        production_digest=production_digest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
