from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load(name: str, filename: str) -> ModuleType:
    scripts = str(Path("scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = Path("scripts") / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_variant_case_failures_include_budget_and_execution_errors() -> None:
    module = _load("run_gate_l_variant_test", "run_gate_l_variant.py")
    failures = module._case_failures(
        [
            {
                "case_id": "ok",
                "budget_compliance": True,
                "budget_violations": [],
            },
            {
                "case_id": "bad",
                "budget_compliance": False,
                "budget_violations": ["execution_error", "incomplete_usage_accounting"],
            },
        ]
    )
    assert failures == [
        {
            "case_id": "bad",
            "violations": ["execution_error", "incomplete_usage_accounting"],
        }
    ]


def test_formal_runner_preserves_preflight_on_failed_closed_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load("run_gate_l_formal_test", "run_gate_l_formal.py")
    monkeypatch.chdir(tmp_path)
    source_sha = "a" * 40
    manifest_path = tmp_path / "manifest.json"
    strategy_path = tmp_path / "strategy.json"
    price_path = tmp_path / "price.json"
    output_dir = tmp_path / "output"
    _write_json(manifest_path, {"placeholder": True})
    _write_json(price_path, {"version": "test"})
    _write_json(strategy_path, {"price_table": "price.json"})
    manifest = {
        "formal_contract_version": "gate-l.formal.v1",
        "version": "v3-test",
        "frozen_artifact_bundle_sha256": "b" * 64,
        "required_provider_environment": [],
    }
    monkeypatch.setattr(module, "_git_sha", lambda: source_sha)
    monkeypatch.setattr(module, "_git_clean", lambda: True)
    monkeypatch.setattr(module, "verify_contract", lambda *args, **kwargs: manifest)

    async def fake_run_variant(args) -> int:
        identity = {
            "repo_sha": source_sha,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        }
        _write_json(
            args.output_dir / "run-record.json",
            {
                "formal_run": True,
                "formal_execution_eligible": False,
                "execution_identity": identity,
            },
        )
        return 2

    monkeypatch.setattr(module, "run_variant", fake_run_variant)
    result = asyncio.run(
        module.execute(
            argparse.Namespace(
                manifest=manifest_path,
                strategy=strategy_path,
                output_dir=output_dir,
                case_id=[],
            )
        )
    )
    assert result == 2
    preflight = output_dir / "formal-preflight.json"
    assert preflight.is_file()
    run_record = json.loads((output_dir / "run-record.json").read_text(encoding="utf-8"))
    assert run_record["formal_execution_eligible"] is False
    assert (
        run_record["formal_contract"]["preflight_sha256"]
        == hashlib.sha256(preflight.read_bytes()).hexdigest()
    )
