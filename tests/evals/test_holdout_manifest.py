from __future__ import annotations

import json
from pathlib import Path


def test_holdout_manifest_does_not_embed_cases() -> None:
    manifest = json.loads(Path("evals/v0_6/holdout_manifest.json").read_text(encoding="utf-8"))

    assert manifest["raw_cases_committed"] is False
    assert manifest["expected_case_count"] == sum(manifest["category_counts"].values())
    assert "cases" not in manifest
