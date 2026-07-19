from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    path = Path("scripts/gate_l_artifact_chain.py")
    spec = importlib.util.spec_from_file_location("gate_l_artifact_chain", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_sums(directory: Path, relative_paths: list[str]) -> None:
    lines = [f"{_sha256(directory / path)}  {path}" for path in relative_paths]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_verify_freeze_bundle_rejects_tampering(tmp_path: Path) -> None:
    module = _load_module()
    source_sha = "a" * 40
    bundle = tmp_path / "freeze"
    bundle.mkdir()
    manifest = {
        "formal_contract_version": "gate-l.formal.v1",
        "contract_version": "gate-l.acceptance.v3",
        "status": "frozen_pending_execution",
        "scientific_behavior_cutoff_sha": source_sha,
        "case_file_sha256": "b" * 64,
        "frozen_artifact_bundle_sha256": "c" * 64,
    }
    _write_json(bundle / "manifest.json", manifest)
    _write_json(
        bundle / "freeze-record.json",
        {
            "source_sha": source_sha,
            "github_run_id": "123",
            "manifest_sha256": _sha256(bundle / "manifest.json"),
        },
    )
    (bundle / "gate-l-formal-freeze.tgz").write_bytes(b"archive")
    paths = ["manifest.json", "freeze-record.json", "gate-l-formal-freeze.tgz"]
    _write_sums(bundle, paths)

    result = module.verify_freeze_bundle(
        bundle,
        expected_source_sha=source_sha,
        expected_run_id="123",
    )
    assert result["manifest_sha256"] == _sha256(bundle / "manifest.json")

    (bundle / "manifest.json").write_text("{}\n", encoding="utf-8")
    try:
        module.verify_freeze_bundle(
            bundle,
            expected_source_sha=source_sha,
            expected_run_id="123",
        )
    except ValueError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("tampered freeze manifest must be rejected")


def test_verify_execution_requires_all_evidence_checksums(tmp_path: Path) -> None:
    module = _load_module()
    source_sha = "d" * 40
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    case_file = repo_root / "evals/holdout.jsonl"
    case_file.parent.mkdir(parents=True)
    case_ids = [f"case-{index:02d}" for index in range(16)]
    case_file.write_text(
        "".join(json.dumps({"case_id": case_id}) + "\n" for case_id in case_ids),
        encoding="utf-8",
    )
    manifest_path = repo_root / "manifest.json"
    manifest = {
        "scientific_behavior_cutoff_sha": source_sha,
        "case_file": "evals/holdout.jsonl",
        "frozen_artifact_bundle_sha256": "e" * 64,
    }
    _write_json(manifest_path, manifest)
    manifest_sha = _sha256(manifest_path)

    bundle = tmp_path / "execution"
    evidence_dir = bundle / "per-case"
    evidence_dir.mkdir(parents=True)
    identity = {"repo_sha": source_sha, "manifest_sha256": manifest_sha}
    for case_id in case_ids:
        _write_json(
            evidence_dir / f"{case_id}.json",
            {
                "case_id": case_id,
                "execution_identity": identity,
                "output_digest": "1" * 64,
                "trace_digest": "2" * 64,
            },
        )
    _write_json(
        bundle / "formal-preflight.json",
        {"runtime_sha": source_sha, "manifest_sha256": manifest_sha},
    )
    preflight_sha = _sha256(bundle / "formal-preflight.json")
    _write_json(
        bundle / "run-record.json",
        {
            "formal_run": True,
            "formal_execution_eligible": True,
            "case_count": 16,
            "selected_case_ids": [],
            "execution_identity": identity,
            "formal_contract": {
                "preflight_sha256": preflight_sha,
                "artifact_bundle_sha256": "e" * 64,
            },
            "cases": [{"case_id": case_id} for case_id in case_ids],
        },
    )
    _write_sums(bundle, ["run-record.json", "formal-preflight.json"])

    try:
        module.verify_execution_bundle(
            bundle,
            manifest_path=manifest_path,
            expected_source_sha=source_sha,
            repo_root=repo_root,
        )
    except ValueError as exc:
        assert "missing per-case evidence" in str(exc)
    else:
        raise AssertionError("unchecksummed evidence files must be rejected")

    paths = ["run-record.json", "formal-preflight.json"] + [
        f"per-case/{case_id}.json" for case_id in case_ids
    ]
    _write_sums(bundle, paths)
    result = module.verify_execution_bundle(
        bundle,
        manifest_path=manifest_path,
        expected_source_sha=source_sha,
        repo_root=repo_root,
    )
    assert result["case_count"] == 16
    assert result["formal_execution_eligible"] is True
