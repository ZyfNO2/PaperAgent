"""Freeze and verify the full evidence identity for a formal Gate L v3 run.

This module complements ``gate_l_acceptance_v3.py``. The acceptance manifest
remains compatible with the existing v3 scorer, while the formal contract binds
all scientific-behaviour inputs that must remain unchanged between freeze and
execution: holdout cases, prompts, policy versions, implementation files,
strategy profiles, and price tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from gate_l_acceptance_v3 import DEFAULT_THRESHOLDS, validate_cases

from paperagent.academic_methodology import (
    METHOD_AUDIT_POLICY_VERSION,
    METHOD_PLAN_CONTRACT_VERSION,
)
from paperagent.prompts import all_prompts

FORMAL_CONTRACT_VERSION = "gate-l.formal.v1"
ACCEPTANCE_CONTRACT_VERSION = "gate-l.acceptance.v3"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SECRET_KEYS = {"api_key", "apikey", "secret", "token", "password", "credential"}
_SECRET_SUFFIXES = (
    "_api_key",
    "_secret",
    "_password",
    "_credential",
    "_access_token",
    "_auth_token",
)
_REQUIRED_ATTESTATIONS = (
    "independent_from_remediation",
    "not_used_for_tuning",
    "no_access_to_previous_holdout_outputs",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        values.append(value)
    return values


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_relative_path(raw: object, *, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} must contain a non-empty repository-relative path")
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or path.as_posix() in {".", ""}:
        raise ValueError(f"{field} must be a safe repository-relative path: {raw!r}")
    return path.as_posix()


def _repo_relative(path: Path, repo_root: Path, *, field: str) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} must be inside the repository") from exc
    return _safe_relative_path(relative.as_posix(), field=field)


def _paths(value: object, *, field: str, minimum: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} path(s)")
    result = [_safe_relative_path(item, field=field) for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicate paths")
    return result


def _ensure_no_secrets(value: object, *, location: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower().replace("-", "_")
            if lowered in _SECRET_KEYS or lowered.endswith(_SECRET_SUFFIXES):
                raise ValueError(f"{location} contains forbidden credential field {key!r}")
            _ensure_no_secrets(nested, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _ensure_no_secrets(nested, location=f"{location}[{index}]")


def _artifact_record(repo_root: Path, path: str, *, kind: str) -> dict[str, str]:
    absolute = repo_root / path
    if not absolute.is_file():
        raise ValueError(f"missing frozen {kind} file: {path}")
    return {"kind": kind, "path": path, "sha256": _sha256(absolute)}


def _runtime_prompt_snapshot(
    repo_root: Path,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    versions: dict[str, str] = {}
    records: list[dict[str, str]] = []
    for prompt in all_prompts():
        versions[prompt.task] = prompt.version
        path = f"src/paperagent/prompts/v0_1/{prompt.task}.md"
        records.append(_artifact_record(repo_root, path, kind="prompt"))
    records.append(
        _artifact_record(
            repo_root,
            "src/paperagent/prompts/registry.py",
            kind="prompt_registry",
        )
    )
    return versions, records


def _runtime_policy_snapshot() -> dict[str, str]:
    return {
        "method_plan_contract_version": METHOD_PLAN_CONTRACT_VERSION,
        "method_audit_policy_version": METHOD_AUDIT_POLICY_VERSION,
    }


def _validate_attestation(attestation: dict[str, Any], case_digest: str) -> None:
    for field in ("author_or_owner", "role", "authored_at_utc"):
        value = attestation.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"attestation.{field} is required")
    for field in _REQUIRED_ATTESTATIONS:
        if attestation.get(field) is not True:
            raise ValueError(f"attestation.{field} must be true")
    declared = attestation.get("case_file_sha256")
    if declared != case_digest:
        raise ValueError("attestation.case_file_sha256 must exactly match the case file")


def _validate_strategy(repo_root: Path, path: str) -> None:
    profile = _read_json(repo_root / path)
    _ensure_no_secrets(profile, location=path)
    for field in ("strategy_id", "provider", "model", "base_url", "price_table"):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path} requires {field}")
    declared_price = _safe_relative_path(
        profile["price_table"], field=f"{path}.price_table"
    )
    if not (repo_root / declared_price).is_file():
        raise ValueError(f"{path} references missing price table: {declared_price}")


def _source_sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ValueError("source_sha must be a full 40-character lowercase commit SHA")
    return value


def freeze_contract(
    spec_path: Path,
    manifest_path: Path,
    *,
    source_sha: str,
    repo_root: Path = Path("."),
    prompt_snapshot: Callable[
        [Path], tuple[dict[str, str], list[dict[str, str]]]
    ] = _runtime_prompt_snapshot,
    policy_snapshot: Callable[[], dict[str, str]] = _runtime_policy_snapshot,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    spec_relative = _repo_relative(spec_path, repo_root, field="spec")
    spec = _read_json(spec_path)
    holdout_version = spec.get("holdout_version")
    if not isinstance(holdout_version, str) or not holdout_version.startswith("v3-"):
        raise ValueError("holdout_version must start with 'v3-'")
    frozen_source_sha = _source_sha(source_sha)
    cases_path = _safe_relative_path(spec.get("cases"), field="cases")
    attestation_path = _safe_relative_path(
        spec.get("attestation"), field="attestation"
    )
    behavior_files = _paths(spec.get("behavior_files"), field="behavior_files")
    strategy_profiles = _paths(
        spec.get("strategy_profiles"), field="strategy_profiles"
    )
    price_tables = _paths(spec.get("price_tables"), field="price_tables")
    required_environment = spec.get("required_provider_environment", [])
    if not isinstance(required_environment, list) or any(
        not isinstance(item, str) or not item.strip()
        for item in required_environment
    ):
        raise ValueError("required_provider_environment must be a list of non-empty names")
    if len(required_environment) != len(set(required_environment)):
        raise ValueError("required_provider_environment must not contain duplicates")
    if any("=" in item for item in required_environment):
        raise ValueError("required_provider_environment must contain names, never values")

    case_absolute = repo_root / cases_path
    cases = _read_jsonl(case_absolute)
    errors = validate_cases(cases, expected_version=holdout_version)
    if errors:
        raise ValueError("\n".join(errors))
    case_digest = _sha256(case_absolute)
    attestation = _read_json(repo_root / attestation_path)
    _validate_attestation(attestation, case_digest)

    records = [
        _artifact_record(repo_root, spec_relative, kind="freeze_spec"),
        _artifact_record(repo_root, cases_path, kind="holdout_cases"),
        _artifact_record(
            repo_root,
            attestation_path,
            kind="holdout_attestation",
        ),
    ]
    records.extend(
        _artifact_record(repo_root, path, kind="behavior")
        for path in behavior_files
    )
    for path in strategy_profiles:
        _validate_strategy(repo_root, path)
        records.append(
            _artifact_record(repo_root, path, kind="strategy_profile")
        )
    records.extend(
        _artifact_record(repo_root, path, kind="price_table")
        for path in price_tables
    )
    prompt_versions, prompt_records = prompt_snapshot(repo_root)
    records.extend(prompt_records)

    price_set = set(price_tables)
    for path in strategy_profiles:
        profile = _read_json(repo_root / path)
        declared_price = _safe_relative_path(
            profile["price_table"], field=f"{path}.price_table"
        )
        if declared_price not in price_set:
            raise ValueError(
                f"{path} price table {declared_price!r} must also appear in price_tables"
            )

    normalized_records = sorted(
        records, key=lambda item: (item["kind"], item["path"])
    )
    manifest = {
        "version": holdout_version,
        "contract_version": ACCEPTANCE_CONTRACT_VERSION,
        "formal_contract_version": FORMAL_CONTRACT_VERSION,
        "status": "frozen_pending_execution",
        "frozen_at_utc": datetime.now(tz=UTC).isoformat(),
        "scientific_behavior_cutoff_sha": frozen_source_sha,
        "planning_prompt_version": prompt_versions["planning"],
        "prompt_versions": prompt_versions,
        "policy_versions": policy_snapshot(),
        "case_file": cases_path,
        "case_file_sha256": case_digest,
        "raw_cases_committed": True,
        "expected_case_count": 16,
        "expected_category_counts": {
            category: sum(case.get("category") == category for case in cases)
            for category in (
                "in_domain",
                "ood",
                "insufficient_evidence",
                "adversarial",
            )
        },
        "author_attestation": attestation,
        "acceptance_thresholds": DEFAULT_THRESHOLDS,
        "strategy_profiles": strategy_profiles,
        "price_tables": price_tables,
        "required_provider_environment": required_environment,
        "frozen_artifacts": normalized_records,
        "frozen_artifact_bundle_sha256": _canonical_digest(normalized_records),
        "freeze_spec_path": spec_relative,
        "freeze_spec_sha256": _sha256(spec_path),
        "note": (
            "Formal Gate L input identity. Any case, prompt, policy, behavior file, "
            "strategy, price table, threshold, or source-SHA change requires a new "
            "holdout version."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _verify_acceptance_manifest(
    manifest_path: Path, repo_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _read_json(manifest_path)
    if manifest.get("contract_version") != ACCEPTANCE_CONTRACT_VERSION:
        raise ValueError(f"contract_version must be {ACCEPTANCE_CONTRACT_VERSION}")
    if manifest.get("status") != "frozen_pending_execution":
        raise ValueError("manifest status must be frozen_pending_execution")
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("manifest version is required")
    case_path = _safe_relative_path(manifest.get("case_file"), field="case_file")
    case_absolute = repo_root / case_path
    if not case_absolute.is_file():
        raise ValueError(f"case file does not exist: {case_path}")
    if _sha256(case_absolute) != manifest.get("case_file_sha256"):
        raise ValueError("case file digest mismatch: frozen holdout was modified")
    cases = _read_jsonl(case_absolute)
    errors = validate_cases(cases, expected_version=version)
    if errors:
        raise ValueError("\n".join(errors))
    return manifest, cases


def verify_contract(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
    runtime_sha: str | None = None,
    strategy_path: Path | None = None,
    price_table_path: Path | None = None,
    prompt_snapshot: Callable[
        [Path], tuple[dict[str, str], list[dict[str, str]]]
    ] = _runtime_prompt_snapshot,
    policy_snapshot: Callable[[], dict[str, str]] = _runtime_policy_snapshot,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest, _ = _verify_acceptance_manifest(manifest_path, repo_root)
    if manifest.get("formal_contract_version") != FORMAL_CONTRACT_VERSION:
        raise ValueError(
            f"formal_contract_version must be {FORMAL_CONTRACT_VERSION}"
        )
    frozen_sha = _source_sha(manifest.get("scientific_behavior_cutoff_sha"))
    if runtime_sha is not None and _source_sha(runtime_sha) != frozen_sha:
        raise ValueError(
            f"runtime SHA {runtime_sha} does not match frozen scientific behavior "
            f"SHA {frozen_sha}"
        )

    artifacts = manifest.get("frozen_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("formal manifest must contain frozen_artifacts")
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("invalid frozen artifact entry")
        path = _safe_relative_path(
            item.get("path"), field="frozen_artifacts.path"
        )
        kind = item.get("kind")
        digest = item.get("sha256")
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(digest, str)
            or not digest
        ):
            raise ValueError(f"invalid frozen artifact metadata for {path}")
        if path in seen:
            raise ValueError(f"duplicate frozen artifact path: {path}")
        seen.add(path)
        absolute = repo_root / path
        if not absolute.is_file():
            raise ValueError(f"missing frozen artifact: {path}")
        actual = _sha256(absolute)
        if actual != digest:
            raise ValueError(f"frozen artifact digest mismatch: {path}")
        normalized.append({"kind": kind, "path": path, "sha256": digest})
    normalized.sort(key=lambda item: (item["kind"], item["path"]))
    if _canonical_digest(normalized) != manifest.get(
        "frozen_artifact_bundle_sha256"
    ):
        raise ValueError("frozen artifact bundle digest mismatch")

    prompt_versions, _ = prompt_snapshot(repo_root)
    if manifest.get("prompt_versions") != prompt_versions:
        raise ValueError("runtime prompt versions do not match the frozen manifest")
    if manifest.get("policy_versions") != policy_snapshot():
        raise ValueError(
            "runtime methodology policy versions do not match the frozen manifest"
        )

    if strategy_path is not None:
        strategy = _safe_relative_path(strategy_path.as_posix(), field="strategy")
        if strategy not in manifest.get("strategy_profiles", []):
            raise ValueError(
                f"strategy profile is not frozen in the manifest: {strategy}"
            )
    if price_table_path is not None:
        price = _safe_relative_path(
            price_table_path.as_posix(), field="price_table"
        )
        if price not in manifest.get("price_tables", []):
            raise ValueError(
                f"price table is not frozen in the manifest: {price}"
            )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Formal Gate L v3 contract utilities"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--spec", type=Path, required=True)
    freeze.add_argument("--manifest-out", type=Path, required=True)
    freeze.add_argument("--source-sha", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--runtime-sha")
    verify.add_argument("--strategy", type=Path)
    verify.add_argument("--price-table", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "freeze":
            manifest = freeze_contract(
                args.spec,
                args.manifest_out,
                source_sha=args.source_sha,
            )
            print(
                "Formal Gate L manifest frozen: "
                f"version={manifest['version']} "
                f"bundle={manifest['frozen_artifact_bundle_sha256']}"
            )
        else:
            manifest = verify_contract(
                args.manifest,
                runtime_sha=args.runtime_sha,
                strategy_path=args.strategy,
                price_table_path=args.price_table,
            )
            print(
                "Formal Gate L manifest verified: "
                f"version={manifest['version']} "
                f"source={manifest['scientific_behavior_cutoff_sha']}"
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Formal Gate L contract error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
