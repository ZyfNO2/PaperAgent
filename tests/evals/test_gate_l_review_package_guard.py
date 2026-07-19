from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts = str(Path("scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = Path("scripts/gate_l_review_package_guard.py")
    spec = importlib.util.spec_from_file_location("gate_l_review_package_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_guard_rejects_hidden_case_identity(tmp_path: Path) -> None:
    module = _load_module()
    cases = [{"case_id": f"case-{index:02d}"} for index in range(16)]
    module.verify_manifest = lambda _: ({"version": "v3-test"}, cases)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    package = tmp_path / "package.json"
    package_value = {
        "gate": "L",
        "holdout_version": "v3-test",
        "blinded": True,
        "cases": [
            {"arm_id": f"arm-{index:03d}", "review_output": {"text": "ok"}} for index in range(16)
        ],
    }
    _write(package, package_value)
    mapping = tmp_path / "mapping.json"
    _write(
        mapping,
        {
            "holdout_version": "v3-test",
            "review_package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "arms": [
                {"arm_id": f"arm-{index:03d}", "case_id": case["case_id"]}
                for index, case in enumerate(cases)
            ],
        },
    )
    result = module.validate_review_package(manifest, package, mapping)
    assert result["case_count"] == 16

    package_value["cases"][0]["case_id"] = cases[0]["case_id"]
    _write(package, package_value)
    try:
        module.validate_review_package(manifest, package, mapping)
    except ValueError as exc:
        assert "forbidden field" in str(exc)
    else:
        raise AssertionError("raw case identity must be rejected")
