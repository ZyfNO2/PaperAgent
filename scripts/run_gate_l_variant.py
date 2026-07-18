"""Run one predeclared Gate L strategy against a frozen v3 holdout."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gate_l_acceptance_v3 import allowed_terminals, verify_manifest
from run_gate_l_v2 import _execute_case, _git_clean, _sha256

from paperagent.api.real_executor import build_real_task_executor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.prompts import get_prompt
from paperagent.providers.config import load_provider_config

ALLOWED_ENV_PREFIXES = ("PAPERAGENT_", "SEMANTIC_SCHOLAR_")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile(path: Path) -> dict[str, Any]:
    profile = _read(path)
    for field in ("strategy_id", "provider", "model", "base_url", "price_table"):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"strategy profile requires {field}")
    if "api_key" in profile or "secret" in profile:
        raise ValueError("strategy profiles must not contain credentials")
    environment = profile.get("environment", {})
    if not isinstance(environment, dict):
        raise ValueError("strategy environment must be an object")
    for key, value in environment.items():
        if not isinstance(key, str) or not key.startswith(ALLOWED_ENV_PREFIXES):
            raise ValueError(f"unsupported environment override: {key}")
        if not isinstance(value, str):
            raise ValueError(f"environment override {key} must be a string")
    literature = profile.get("literature", {})
    if not isinstance(literature, dict):
        raise ValueError("strategy literature settings must be an object")
    allowed_literature = {
        "provider_timeout_seconds",
        "round_deadline_seconds",
        "enable_arxiv_fallback",
    }
    unknown = set(literature) - allowed_literature
    if unknown:
        raise ValueError(f"unsupported literature settings: {sorted(unknown)}")
    return profile


def _apply_environment(profile: dict[str, Any]) -> None:
    for key, value in profile.get("environment", {}).items():
        os.environ[key] = value


async def run(args: argparse.Namespace) -> int:
    profile = _profile(args.strategy)
    _apply_environment(profile)
    manifest, all_cases = verify_manifest(args.manifest)
    prompt = get_prompt("planning")
    if prompt.version != manifest.get("planning_prompt_version"):
        raise ValueError("runtime planning prompt does not match frozen manifest")

    requested = set(args.case_id)
    cases = all_cases
    if requested:
        cases = [case for case in all_cases if case["case_id"] in requested]
        missing = requested - {case["case_id"] for case in cases}
        if missing:
            raise ValueError(f"unknown case IDs: {sorted(missing)}")
    formal_run = not requested and len(cases) == len(all_cases) == 16
    clean_tree = _git_clean()

    provider_config = load_provider_config(
        provider=profile["provider"],
        model=profile["model"],
        base_url=profile["base_url"],
    )
    price_table_path = Path(profile["price_table"])
    price_table = load_price_table(price_table_path)
    literature = profile.get("literature", {})
    executor = build_real_task_executor(
        provider_config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            provider_timeout_seconds=float(
                literature.get("provider_timeout_seconds", 10.0)
            ),
            round_deadline_seconds=float(
                literature.get("round_deadline_seconds", 25.0)
            ),
            enable_arxiv_fallback=bool(
                literature.get("enable_arxiv_fallback", True)
            ),
        ),
        price_table=price_table,
    )
    identity = {
        "repo_sha": os.environ.get("GITHUB_SHA", "local"),
        "clean_tree": clean_tree,
        "scientific_behavior_cutoff_sha": manifest[
            "scientific_behavior_cutoff_sha"
        ],
        "planning_prompt_version": prompt.version,
        "provider": provider_config.provider.value,
        "model": provider_config.model,
        "base_url": str(provider_config.base_url),
        "strategy_profile": profile["strategy_id"],
        "strategy_profile_sha256": _digest(args.strategy),
        "price_table_path": price_table_path.as_posix(),
        "price_table_sha256": _sha256(price_table_path),
        "manifest_path": args.manifest.as_posix(),
        "manifest_sha256": _sha256(args.manifest),
        "case_file_sha256": manifest["case_file_sha256"],
        "python_version": sys.version,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
    }

    evidence_dir = args.output_dir / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        runtime_case = dict(case)
        runtime_case["expected_terminal"] = sorted(allowed_terminals(case))[0]
        evidence = await _execute_case(
            runtime_case,
            executor,
            index,
            identity,
        )
        evidence.pop("expected_terminal", None)
        evidence["expected_terminals"] = sorted(allowed_terminals(case))
        evidence["strategy_profile"] = profile["strategy_id"]
        results.append(evidence)
        (evidence_dir / f"{case['case_id']}.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    global_failures: list[str] = []
    if formal_run and clean_tree is not True:
        global_failures.append("clean_tree_not_verified")
    run_record = {
        "gate": "L",
        "contract_version": manifest["contract_version"],
        "holdout_version": manifest["version"],
        "strategy_id": profile["strategy_id"],
        "formal_run": formal_run,
        "formal_execution_eligible": formal_run and not global_failures,
        "selected_case_ids": sorted(requested),
        "execution_identity": identity,
        "started_utc": min(
            (item["started_utc"] for item in results),
            default=None,
        ),
        "finished_utc": datetime.now(tz=UTC).isoformat(),
        "case_count": len(results),
        "terminal_summary": dict(Counter(item["terminal"] for item in results)),
        "global_failures": global_failures,
        "cases": [
            {
                "case_id": item["case_id"],
                "category": item["category"],
                "terminal": item["terminal"],
                "expected_terminals": item["expected_terminals"],
                "budget_compliance": item["budget_compliance"],
                "output_digest": item["output_digest"],
                "trace_digest": item["trace_digest"],
            }
            for item in results
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not formal_run:
        print("Targeted execution is diagnostic-only.")
    if global_failures:
        print(f"Formal execution integrity failure: {global_failures}")
        return 2
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return asyncio.run(run(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L variant run error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
