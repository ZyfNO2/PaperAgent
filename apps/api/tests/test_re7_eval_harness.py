"""Unit tests for the Re7.6 evaluation harness (scripts/re6_eval.py)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


def _load_re6_eval_module():
    """Load the harness via importlib so it does not need to be a package."""
    root = Path(__file__).resolve().parents[3]
    script_path = root / "scripts" / "re6_eval.py"
    spec = importlib.util.spec_from_file_location("re6_eval", str(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def re6_eval():
    return _load_re6_eval_module()


@pytest.fixture
def workdir():
    """Provide a unique writable directory under the project root."""
    root = Path(__file__).resolve().parents[3]
    base = root / "tmp" / "test_re7_eval"
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid.uuid4().hex
    path.mkdir()
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_harness_creates_manifest_and_junit(re6_eval, workdir):
    """Mock run on two synthetic fixtures should produce manifest + JUnit XML."""
    fixtures = workdir / "fixtures"
    (fixtures / "hidden_ood").mkdir(parents=True)
    (fixtures / "failure").mkdir(parents=True)

    pass_case = {
        "case_id": "OOD-PASS",
        "topic": "a synthetic OOD topic",
        "domain": "OOD",
        "expected_verdict": "GO",
        "ood_category": "A",
        "rationale": "cross-discipline fusion",
    }
    fail_case = {
        "case_id": "FAIL-MISS",
        "topic": "a synthetic failure topic",
        "failure_type": "missing_injection",
        "description": "intentionally missing injection block",
    }

    (fixtures / "hidden_ood" / "ood_pass.json").write_text(
        json.dumps(pass_case), encoding="utf-8"
    )
    (fixtures / "failure" / "fail_missing.json").write_text(
        json.dumps(fail_case), encoding="utf-8"
    )

    output_dir = workdir / "out"
    run_dir = re6_eval.run_eval(
        mock=True,
        fixtures_dir=fixtures,
        holdout=False,
        output_dir=output_dir,
    )

    assert run_dir.exists()
    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_cases"] == 2
    assert manifest["counts"]["pass"] == 1
    assert manifest["counts"]["fail"] == 1

    xml_path = run_dir / "targeted_test_report.xml"
    assert xml_path.exists()
    tree = ET.parse(xml_path)
    root = tree.getroot()
    cases = root.findall(".//testcase")
    assert len(cases) == 2
    assert {c.attrib.get("name") for c in cases} == {"OOD-PASS", "FAIL-MISS"}

    taxonomy_path = run_dir / "failure_taxonomy.json"
    assert taxonomy_path.exists()
    trace_path = run_dir / "trace_summary.json"
    assert trace_path.exists()
