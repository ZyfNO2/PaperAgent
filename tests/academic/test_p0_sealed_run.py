from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paperagent.academic.p0_sealed_run import (
    P0PublicInputPaths,
    P0SealedRunError,
    load_sealed_run,
    run_p0_blinded,
    score_sealed_run,
    validate_public_inputs,
)

ROOT = Path(__file__).parents[2]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _public_fixture(tmp_path: Path) -> tuple[P0PublicInputPaths, Path]:
    schema = tmp_path / "schema.json"
    golden_fixture = tmp_path / "golden.json"
    corpus = tmp_path / "corpus.jsonl"
    questions = tmp_path / "questions.blinded.jsonl"
    question_manifest = tmp_path / "question_manifest.json"
    artifact_manifest = tmp_path / "artifact_manifest.json"
    schema.write_text("{\"schema\": true}", encoding="utf-8")
    golden_fixture.write_text("{\"golden\": true}", encoding="utf-8")
    _write_jsonl(corpus, [{"entry_id": "paper-0001"}])
    question_rows = [
        {
            "schema_version": "academic-rag-p0-blinded-question.v1",
            "question_id": f"Q{index:02d}",
            "question_type": ("text", "figure", "table", "equation")[(index - 1) // 8],
            "question": f"Human verified question {index}",
            "corpus_id": "academic-rag-h0-v1",
            "blind": True,
            "authoring_status": "human_verified",
        }
        for index in range(1, 33)
    ]
    _write_jsonl(questions, question_rows)
    question_manifest.write_text(
        json.dumps(
            {
                "question_file": questions.name,
                "question_count": 32,
                "distribution": {"text": 8, "figure": 8, "table": 8, "equation": 8},
            }
        ),
        encoding="utf-8",
    )
    artifact_manifest.write_text(
        json.dumps(
            {
                "schema_version": "academic-rag-p0-artifact-manifest.v1",
                "required_artifact_types": [f"artifact_{index}" for index in range(8)],
            }
        ),
        encoding="utf-8",
    )
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "protocol_version": "academic-rag-p0-scientific-acceptance.v1",
                "schema_digest": _digest(schema),
                "golden_fixture_digest": _digest(golden_fixture),
                "corpus_manifest_sha256": _digest(corpus),
                "corpus_manifest_entry_count": 1,
                "contract_files": {
                    "schema": {"path": "schema.json", "sha256": _digest(schema)},
                    "golden": {
                        "path": "golden.json",
                        "sha256": _digest(golden_fixture),
                    },
                },
                "question_pack": {
                    "sha256": _digest(questions),
                    "question_manifest_sha256": _digest(question_manifest),
                    "artifact_manifest_sha256": _digest(artifact_manifest),
                },
            }
        ),
        encoding="utf-8",
    )
    return (
        P0PublicInputPaths(
            protocol=protocol,
            schema=schema,
            golden_fixture=golden_fixture,
            corpus_manifest=corpus,
            questions=questions,
            question_manifest=question_manifest,
            artifact_manifest=artifact_manifest,
        ),
        questions,
    )


def _answer(question: dict[str, object]) -> dict[str, object]:
    return {
        "response": f"response for {question['question_id']}",
        "citations": [],
        "contexts": [],
        "trace": {"question_id": question["question_id"]},
    }


def test_public_contract_requires_exact_32_and_real_question_authoring(tmp_path: Path) -> None:
    paths, _ = _public_fixture(tmp_path)
    validated = validate_public_inputs(paths)
    assert len(validated.questions) == 32
    assert validated.digests["questions"] == _digest(paths.questions)


def test_blinded_run_seals_immutably_before_gold_can_be_scored(tmp_path: Path) -> None:
    paths, _ = _public_fixture(tmp_path)
    sealed_path = tmp_path / "run.json"
    sealed = run_p0_blinded(
        paths,
        run_id="run-001",
        output_path=sealed_path,
        answerer=_answer,
        sealed_at_utc="2026-08-02T00:00:00Z",
    )
    assert sealed["question_count"] == 32
    assert len(str(sealed["run_digest"])) == 64
    assert load_sealed_run(sealed_path)["run_digest"] == sealed["run_digest"]
    with pytest.raises(P0SealedRunError, match="overwrite"):
        run_p0_blinded(
            paths,
            run_id="run-002",
            output_path=sealed_path,
            answerer=_answer,
        )


def test_gold_is_read_only_after_valid_seal_and_scorer_receives_both_inputs(
    tmp_path: Path,
) -> None:
    paths, _ = _public_fixture(tmp_path)
    sealed_path = tmp_path / "run.json"
    run_p0_blinded(
        paths,
        run_id="run-002",
        output_path=sealed_path,
        answerer=_answer,
        sealed_at_utc="2026-08-02T00:00:00Z",
    )
    gold_rows = [
        {
            "schema_version": "academic-rag-p0-gold-label.v1",
            "question_id": f"Q{index:02d}",
            "accepted_answers": ["answer"],
            "supporting_paper_ids": ["P01"],
            "evidence_locators": [],
            "allowable_inference": [],
            "forbidden_overclaim": [],
            "should_abstain": False,
            "severe_error_conditions": [],
            "annotator_id": "human-a",
            "reviewer_id": "human-b",
            "annotated_at": "2026-08-02T00:00:00Z",
            "disagreement_resolution": "none",
        }
        for index in range(1, 33)
    ]
    gold_path = tmp_path / "gold.private.jsonl"
    _write_jsonl(gold_path, gold_rows)
    seen = {"called": False}

    def scorer(responses: tuple[dict[str, object], ...], gold: tuple[dict[str, object], ...]):
        seen["called"] = True
        return {"responses": len(responses), "gold": len(gold)}

    result = score_sealed_run(sealed_path, gold_path, scorer=scorer)
    assert result["status"] == "SCORED"
    assert result["scores"] == {"responses": 32, "gold": 32}
    assert seen["called"] is True


def test_gold_marker_in_public_answer_is_rejected(tmp_path: Path) -> None:
    paths, _ = _public_fixture(tmp_path)

    def leaked_answer(question: dict[str, object]) -> dict[str, object]:
        answer = _answer(question)
        answer["gold_locator"] = "must-not-leak"
        return answer

    with pytest.raises(P0SealedRunError, match="private gold"):
        run_p0_blinded(
            paths,
            run_id="run-leaked",
            output_path=tmp_path / "leaked.json",
            answerer=leaked_answer,
        )
