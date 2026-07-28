from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

from paperagent.academic.contracts import EvidenceLocatorView

ROOT = Path(__file__).parents[2]
SCHEMA_SHA256 = "62c3c6bbde000023a95025fdcae53c777fac479ddc9da02a63ea293b0855d2e0"
GOLDEN_SHA256 = "5f8b3b999de2139c6e328966086043663a3012a068636061971926b979ea647d"


def test_paperclaw_canonical_contract_assets_are_frozen() -> None:
    schema = ROOT / "contracts" / "academic.v1.schema.json"
    golden = ROOT / "contracts" / "academic.v1.golden.json"
    assert hashlib.sha256(schema.read_bytes()).hexdigest() == SCHEMA_SHA256
    assert hashlib.sha256(golden.read_bytes()).hexdigest() == GOLDEN_SHA256
    packaged = ROOT / "src" / "paperagent" / "academic" / "wire"
    assert hashlib.sha256(
        (packaged / schema.name).read_bytes()
    ).hexdigest() == SCHEMA_SHA256
    assert hashlib.sha256(
        (packaged / golden.name).read_bytes()
    ).hexdigest() == GOLDEN_SHA256


def test_python311_locator_view_rejects_unknown_schema() -> None:
    payload = json.loads(
        (ROOT / "contracts" / "academic.v1.golden.json").read_text(encoding="utf-8")
    )["evidence_locator"]
    bbox = payload.pop("bounding_box")
    payload["bounding_box"] = tuple(bbox[key] for key in ("x0", "y0", "x1", "y1"))
    assert EvidenceLocatorView.model_validate(payload).schema_version == "academic.v1"

    missing = dict(payload)
    missing.pop("schema_version")
    with pytest.raises(ValidationError):
        EvidenceLocatorView.model_validate(missing)

    payload["schema_version"] = "academic.v2"
    with pytest.raises(ValidationError):
        EvidenceLocatorView.model_validate(payload)


def test_python311_structural_schema_rejects_incomplete_wire_payloads() -> None:
    schema = json.loads(
        (ROOT / "contracts" / "academic.v1.schema.json").read_text(encoding="utf-8")
    )
    golden = json.loads(
        (ROOT / "contracts" / "academic.v1.golden.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    for key in (
        "paper_record",
        "academic_object",
        "evidence_locator",
        "evidence_bundle",
        "memory_snapshot",
        "artifact_revision",
    ):
        validator.validate(golden[key])
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({"schema_version": "academic.v1"})
