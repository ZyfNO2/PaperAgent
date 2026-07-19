from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts = str(Path("scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = Path("scripts/gate_l_formal_audit.py")
    spec = importlib.util.spec_from_file_location("gate_l_formal_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"version": "v3-test"})
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    cases = [{"case_id": f"case-{index:02d}"} for index in range(16)]
    for case in cases:
        _write_json(evidence_dir / f"{case['case_id']}.json", case)
    return manifest, evidence_dir, cases


def test_audit_template_is_fail_closed(tmp_path: Path) -> None:
    module = _load_module()
    manifest, evidence_dir, cases = _fixture(tmp_path)
    module.verify_manifest = lambda _: ({"version": "v3-test"}, cases)

    template = module.build_template(manifest, evidence_dir)

    assert template["audit_complete"] is False
    assert template["auditor_id"].startswith("REPLACE_WITH")
    assert all(value is False for value in template["independence_attestation"].values())
    assert len(template["cases"]) == 16


def test_completed_audit_derives_rates_from_case_counts(tmp_path: Path) -> None:
    module = _load_module()
    manifest, evidence_dir, cases = _fixture(tmp_path)
    module.verify_manifest = lambda _: ({"version": "v3-test"}, cases)
    audit = module.build_template(manifest, evidence_dir)
    audit["audit_complete"] = True
    audit["auditor_id"] = "expert-auditor-001"
    audit["independence_attestation"] = {field: True for field in module._ATTESTATIONS}
    for item in audit["cases"]:
        for flag in module._REVIEW_FLAGS:
            item[flag] = True
        item["noncritical_claims_reviewed"] = 10
        item["citations_reviewed"] = 5
    audit["cases"][0]["noncritical_unsupported_claims"] = 2
    audit["cases"][0]["citation_mismatches"] = 1
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, audit)

    normalized = module.normalize_completed_audit(manifest, evidence_dir, audit_path)

    assert normalized["audit_complete"] is True
    assert normalized["noncritical_unsupported_claim_rate"] == 2 / 160
    assert normalized["citation_mismatch_rate"] == 1 / 80
    assert normalized["content_totals"]["noncritical_claims_reviewed"] == 160


def test_completed_audit_rejects_unreviewed_case(tmp_path: Path) -> None:
    module = _load_module()
    manifest, evidence_dir, cases = _fixture(tmp_path)
    module.verify_manifest = lambda _: ({"version": "v3-test"}, cases)
    audit = module.build_template(manifest, evidence_dir)
    audit["audit_complete"] = True
    audit["auditor_id"] = "expert-auditor-001"
    audit["independence_attestation"] = {field: True for field in module._ATTESTATIONS}
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, audit)

    try:
        module.normalize_completed_audit(manifest, evidence_dir, audit_path)
    except ValueError as exc:
        assert "content-review flags" in str(exc)
    else:
        raise AssertionError("incomplete case review must be rejected")
