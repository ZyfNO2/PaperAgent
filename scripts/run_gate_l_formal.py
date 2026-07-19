"""Execute a formal Gate L v3 run only after exact contract preflight succeeds."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from gate_l_formal_contract import verify_contract
from run_gate_l_variant import run as run_variant

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _git_sha() -> str:
    environment_sha = os.environ.get("GITHUB_SHA", "").strip().lower()
    if _SHA_RE.fullmatch(environment_sha):
        return environment_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("formal execution requires an exact git commit SHA") from exc
    value = result.stdout.strip().lower()
    if not _SHA_RE.fullmatch(value):
        raise ValueError("git rev-parse did not return a full commit SHA")
    return value


def _git_clean() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("formal execution requires a verifiable clean git tree") from exc
    return not result.stdout.strip()


def _relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError(f"formal run input must be inside the repository: {path}") from exc


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


async def execute(args: argparse.Namespace) -> int:
    if args.case_id:
        raise ValueError("formal execution forbids case filters; run all frozen cases exactly once")
    runtime_sha = _git_sha()
    if not _git_clean():
        raise ValueError("formal execution requires a clean git tree")
    strategy = _relative(args.strategy)
    manifest_path = _relative(args.manifest)
    profile = _read(strategy)
    raw_price_table = profile.get("price_table")
    if not isinstance(raw_price_table, str) or not raw_price_table:
        raise ValueError("strategy profile requires price_table")
    price_table = _relative(Path(raw_price_table))
    manifest = verify_contract(
        manifest_path,
        runtime_sha=runtime_sha,
        strategy_path=strategy,
        price_table_path=price_table,
    )
    missing_environment = [
        name
        for name in manifest.get("required_provider_environment", [])
        if not os.environ.get(name)
    ]
    if missing_environment:
        raise ValueError(
            "missing required provider environment variables: "
            + ", ".join(sorted(missing_environment))
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    preflight = {
        "gate": "L",
        "record_type": "formal_execution_preflight",
        "formal_contract_version": manifest["formal_contract_version"],
        "holdout_version": manifest["version"],
        "verified_at_utc": datetime.now(tz=UTC).isoformat(),
        "runtime_sha": runtime_sha,
        "clean_tree": True,
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "artifact_bundle_sha256": manifest["frozen_artifact_bundle_sha256"],
        "strategy_path": strategy.as_posix(),
        "strategy_sha256": _sha256(strategy),
        "price_table_path": price_table.as_posix(),
        "price_table_sha256": _sha256(price_table),
    }
    preflight_path = args.output_dir / "formal-preflight.json"
    _write(preflight_path, preflight)

    os.environ["GITHUB_SHA"] = runtime_sha
    result = await run_variant(
        SimpleNamespace(
            manifest=manifest_path,
            strategy=strategy,
            output_dir=args.output_dir,
            case_id=[],
        )
    )

    run_record_path = args.output_dir / "run-record.json"
    if not run_record_path.is_file():
        raise ValueError("variant runner did not produce a run record")
    run_record = _read(run_record_path)
    identity = run_record.get("execution_identity")
    if run_record.get("formal_run") is not True:
        raise ValueError("variant runner did not execute the complete frozen corpus")
    if not isinstance(identity, dict) or identity.get("repo_sha") != runtime_sha:
        raise ValueError("run record repository identity does not match formal preflight")
    if identity.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("run record manifest identity does not match formal preflight")

    run_record["formal_contract"] = {
        "preflight_path": preflight_path.as_posix(),
        "preflight_sha256": _sha256(preflight_path),
        "artifact_bundle_sha256": manifest["frozen_artifact_bundle_sha256"],
    }
    _write(run_record_path, run_record)
    eligibility = run_record.get("formal_execution_eligible") is True
    print(
        "Formal Gate L execution evidence completed: "
        f"eligible={eligibility} result_code={result} path={run_record_path}"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an exact formal Gate L v3 execution")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return asyncio.run(execute(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Formal Gate L execution error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
