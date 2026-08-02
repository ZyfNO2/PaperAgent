from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from paperagent.academic.p0_sealed_run import (
    P0PublicInputPaths,
    P0SealedRunError,
    validate_frozen_resource_integrity,
    validate_public_inputs,
    validate_scientific_run_readiness,
)

PAPERAGENT_ROOT = Path(__file__).parents[2]


def _paths_from_real_repositories() -> P0PublicInputPaths:
    root_value = os.environ.get("PAPERCLAW_ROOT")
    if not root_value:
        pytest.skip("set PAPERCLAW_ROOT to the committed PaperClaw audit worktree")
    paperclaw_root = Path(root_value)
    required = [
        paperclaw_root / "benchmarks/academic_rag/v1/eval/protocol.json",
        paperclaw_root / "benchmarks/academic_rag/v1/eval/questions.blinded.jsonl",
        paperclaw_root / "benchmarks/academic_rag/v1/eval/question_manifest.json",
        paperclaw_root / "benchmarks/academic_rag/v1/eval/artifact_manifest.json",
        paperclaw_root / "benchmarks/academic_rag/v1/frozen_12.json",
        paperclaw_root / "benchmarks/academic_rag/v1/corpus_manifest.jsonl",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        pytest.fail(f"PAPERCLAW_ROOT is not a committed PaperClaw resource root: {missing}")
    return P0PublicInputPaths(
        protocol=PAPERAGENT_ROOT / "evaluation/academic_rag_p0/protocol.json",
        schema=PAPERAGENT_ROOT / "src/paperagent/academic/wire/academic.v1.schema.json",
        golden_fixture=PAPERAGENT_ROOT / "src/paperagent/academic/wire/academic.v1.golden.json",
        corpus_manifest=paperclaw_root / "benchmarks/academic_rag/v1/corpus_manifest.jsonl",
        questions=paperclaw_root / "benchmarks/academic_rag/v1/eval/questions.blinded.jsonl",
        question_manifest=paperclaw_root / "benchmarks/academic_rag/v1/eval/question_manifest.json",
        artifact_manifest=paperclaw_root / "benchmarks/academic_rag/v1/eval/artifact_manifest.json",
        frozen_set=paperclaw_root / "benchmarks/academic_rag/v1/frozen_12.json",
    )


def test_real_committed_cross_repo_resource_integrity_passes() -> None:
    paths = _paths_from_real_repositories()
    validated = validate_frozen_resource_integrity(paths)
    assert validate_public_inputs(paths).digests == validated.digests
    assert len(validated.corpus_entries) == 107
    assert set(validated.frozen_papers) == {f"P{index:02d}" for index in range(1, 13)}
    paperclaw_protocol = json.loads(paths.protocol.read_text(encoding="utf-8"))
    assert paperclaw_protocol["frozen_set"]["frozen_set_id"] == "academic-rag-h0-v1"
    assert paperclaw_protocol["frozen_set"]["count"] == 12


def test_real_committed_placeholder_questions_stop_at_human_authoring_gate() -> None:
    paths = _paths_from_real_repositories()
    validate_public_inputs(paths)
    with pytest.raises(P0SealedRunError, match="HUMAN_QUESTION_AUTHORING"):
        validate_scientific_run_readiness(paths)
