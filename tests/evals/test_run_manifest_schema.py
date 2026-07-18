from __future__ import annotations

import json
from pathlib import Path


def test_run_manifest_schema_requires_reproducibility_fields() -> None:
    schema = json.loads(Path("evals/v0_6/run_manifest.schema.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert {
        "run_id",
        "commit_sha",
        "provider",
        "model",
        "prompt_version",
        "schema_version",
        "corpus_digest",
        "started_at",
    } <= set(schema["required"])
