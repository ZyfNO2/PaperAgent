"""Validate that a Gate L reviewer package is blinded and exactly mapped."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from gate_l_acceptance_v3 import verify_manifest

_FORBIDDEN_KEYS = {
    "case_id",
    "expected_terminal",
    "expected_terminals",
    "expected_decision",
    "execution_identity",
    "provider",
    "model",
    "base_url",
    "strategy_profile",
    "strategy_id",
    "price_table",
    "price_table_path",
    "scientific_behavior_cutoff_sha",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_blinded(value: object, *, case_ids: set[str], location: str = "package") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in _FORBIDDEN_KEYS:
                raise ValueError(f"review package exposes forbidden field {location}.{key}")
            _scan_blinded(nested, case_ids=case_ids, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_blinded(nested, case_ids=case_ids, location=f"{location}[{index}]")
    elif isinstance(value, str) and value in case_ids:
        raise ValueError(f"review package exposes a raw case ID at {location}")


def validate_review_package(
    manifest_path: Path,
    package_path: Path,
    mapping_path: Path,
) -> dict[str, Any]:
    manifest, cases = verify_manifest(manifest_path)
    case_ids = {case["case_id"] for case in cases}
    package = _read(package_path)
    mapping = _read(mapping_path)
    if package.get("gate") != "L" or package.get("blinded") is not True:
        raise ValueError("review package must be a blinded Gate L package")
    if package.get("holdout_version") != manifest["version"]:
        raise ValueError("review package holdout version mismatch")
    raw_cases = package.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != len(case_ids):
        raise ValueError("review package must contain exactly the frozen case count")
    arm_ids: list[str] = []
    for item in raw_cases:
        if not isinstance(item, dict) or not isinstance(item.get("arm_id"), str):
            raise ValueError("review package contains an invalid arm")
        arm_ids.append(item["arm_id"])
    if len(arm_ids) != len(set(arm_ids)):
        raise ValueError("review package arm IDs must be unique")
    _scan_blinded(package, case_ids=case_ids)

    if mapping.get("holdout_version") != manifest["version"]:
        raise ValueError("private mapping holdout version mismatch")
    if mapping.get("review_package_sha256") != _sha256(package_path):
        raise ValueError("private mapping does not bind the review package")
    raw_arms = mapping.get("arms")
    if not isinstance(raw_arms, list):
        raise ValueError("private mapping arms must be a list")
    mapping_by_arm: dict[str, str] = {}
    for item in raw_arms:
        if not isinstance(item, dict):
            raise ValueError("private mapping contains an invalid entry")
        arm_id = item.get("arm_id")
        case_id = item.get("case_id")
        if not isinstance(arm_id, str) or not isinstance(case_id, str):
            raise ValueError("private mapping requires string arm_id and case_id")
        if arm_id in mapping_by_arm:
            raise ValueError(f"duplicate private mapping arm: {arm_id}")
        mapping_by_arm[arm_id] = case_id
    if set(mapping_by_arm) != set(arm_ids):
        raise ValueError("private mapping arm set does not match reviewer package")
    if set(mapping_by_arm.values()) != case_ids:
        raise ValueError("private mapping does not cover the exact frozen case set")
    return {
        "record_type": "verified_blinded_review_package",
        "holdout_version": manifest["version"],
        "case_count": len(case_ids),
        "review_package_sha256": _sha256(package_path),
        "mapping_sha256": _sha256(mapping_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate blinded Gate L review package separation"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_review_package(args.manifest, args.package, args.mapping)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L review-package guard error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
