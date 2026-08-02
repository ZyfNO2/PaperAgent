from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import paperagent.academic.p0_sealed_run as sealed_module
from paperagent.academic.p0_sealed_run import (
    P0PublicInputPaths,
    P0SealedRunError,
    load_sealed_run,
    run_p0_blinded,
    score_sealed_run,
    validate_frozen_resource_integrity,
    validate_public_inputs,
    validate_scientific_run_readiness,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _score(**overrides: object) -> dict[str, object]:
    score: dict[str, object] = {
        "question_count": 32,
        "scored_question_ids": [f"Q{index:02d}" for index in range(1, 33)],
        "critical_unsupported_claims": 0,
        "major_unsupported_claims": 0,
        "critical_citation_mismatches": 0,
        "major_citation_mismatches": 0,
        "false_go": 0,
        "abstention_correct": 0,
        "abstention_incorrect": 0,
        "answerable_correct": 32,
        "answerable_incorrect": 0,
        "artifact_gate_status": "PASS",
        "cross_paper_gate_status": "PASS",
        "gate_statuses": {"artifact": "PASS", "cross_paper": "PASS"},
        "denominator_status": "EXACT_FROZEN_32",
    }
    score.update(overrides)
    return score


def _public_fixture(tmp_path: Path) -> tuple[P0PublicInputPaths, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    schema = tmp_path / "schema.json"
    golden_fixture = tmp_path / "golden.json"
    corpus = tmp_path / "corpus.jsonl"
    questions = tmp_path / "questions.blinded.jsonl"
    question_manifest = tmp_path / "question_manifest.json"
    artifact_manifest = tmp_path / "artifact_manifest.json"
    frozen_set = tmp_path / "frozen_12.json"
    schema.write_text('{"schema": true}', encoding="utf-8")
    golden_fixture.write_text('{"golden": true}', encoding="utf-8")

    corpus_rows = [
        {
            "schema_version": "academic-corpus.v1",
            "entry_id": f"paper-{index:04d}",
            "file_sha256": f"{index:02x}" * 32,
        }
        for index in range(1, 13)
    ]
    _write_jsonl(corpus, corpus_rows)
    frozen_rows = [
        {
            "blind_id": f"P{index:02d}",
            "entry_id": f"paper-{index:04d}",
            "file_sha256": f"{index:02x}" * 32,
            "benchmark_stratum": (
                "crack_detection",
                "reconstruction_3d_stereo",
                "segmentation",
                "concrete_material",
            )[(index - 1) // 3],
            "selection_reason": "fixture",
        }
        for index in range(1, 13)
    ]
    frozen_set.write_text(
        json.dumps(
            {
                "frozen_set_id": "academic-rag-h0-v1",
                "schema_version": "academic-frozen-set.v1",
                "manifest_sha256": _digest(corpus),
                "stratum_counts": {
                    "crack_detection": 3,
                    "reconstruction_3d_stereo": 3,
                    "segmentation": 3,
                    "concrete_material": 3,
                },
                "papers": frozen_rows,
            }
        ),
        encoding="utf-8",
    )
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
                "corpus_manifest_entry_count": 12,
                "contract_files": {
                    "schema": {"path": "schema.json", "sha256": _digest(schema)},
                    "golden": {"path": "golden.json", "sha256": _digest(golden_fixture)},
                },
                "question_pack": {
                    "sha256": _digest(questions),
                    "question_manifest_sha256": _digest(question_manifest),
                    "artifact_manifest_sha256": _digest(artifact_manifest),
                },
                "frozen_set": {
                    "path": "benchmarks/academic_rag/v1/frozen_12.json",
                    "sha256": _digest(frozen_set),
                    "frozen_set_id": "academic-rag-h0-v1",
                    "count": 12,
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
            frozen_set=frozen_set,
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


def _gold_rows() -> list[dict[str, object]]:
    return [
        {
            "schema_version": "academic-rag-p0-gold-label.v1",
            "question_id": f"Q{index:02d}",
            "accepted_answers": ["answer"],
            "supporting_paper_ids": ["P01"],
            "evidence_locators": [],
            "allowable_inference": [],
            "forbidden_overclaim": ["no causal claim"],
            "should_abstain": False,
            "severe_error_conditions": ["wrong paper"],
            "annotator_id": "human-a",
            "reviewer_id": "human-b",
            "annotated_at": "2026-08-02T00:00:00Z",
            "disagreement_resolution": "none",
        }
        for index in range(1, 33)
    ]


def _sealed_fixture(tmp_path: Path) -> tuple[P0PublicInputPaths, Path, Path]:
    paths, _ = _public_fixture(tmp_path)
    sealed_path = tmp_path / "run.json"
    run_p0_blinded(
        paths,
        run_id="run-001",
        output_path=sealed_path,
        answerer=_answer,
        sealed_at_utc="2026-08-02T00:00:00Z",
    )
    gold_path = tmp_path / "gold.private.jsonl"
    _write_jsonl(gold_path, _gold_rows())
    return paths, sealed_path, gold_path


def _rewrite_sealed(path: Path, mutate: Any) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    unsigned = {key: value for key, value in payload.items() if key != "run_digest"}
    payload["run_digest"] = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_public_contract_and_frozen_integrity_require_exact_32_and_12(tmp_path: Path) -> None:
    paths, _ = _public_fixture(tmp_path)
    validated = validate_frozen_resource_integrity(paths)
    assert validate_public_inputs(paths).digests["frozen_set"] == _digest(paths.frozen_set)
    assert len(validated.questions) == 32
    assert set(validated.frozen_papers) == {f"P{index:02d}" for index in range(1, 13)}


def test_blinded_run_seals_immutably_and_binds_frozen_set(tmp_path: Path) -> None:
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
    assert sealed["public_input_digests"]["frozen_set"] == _digest(paths.frozen_set)
    assert load_sealed_run(sealed_path)["run_digest"] == sealed["run_digest"]
    with pytest.raises(P0SealedRunError, match="overwrite"):
        run_p0_blinded(paths, run_id="run-002", output_path=sealed_path, answerer=_answer)


def test_matching_public_inputs_reach_strict_gold_and_decision(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)

    def scorer(
        responses: tuple[dict[str, object], ...], gold: tuple[dict[str, object], ...]
    ) -> dict[str, object]:
        assert len(responses) == len(gold) == 32
        return _score()

    result = score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=scorer)
    assert result["status"] == "SCORED"
    assert result["p0_release"] == "GO"
    assert result["overall_decision"] == "GO"
    assert result["process_blind_isolation_status"] == "BLOCKED_BY_PROCESS_LEVEL_BLIND_ISOLATION"


def test_valid_score_with_blocked_human_gate_is_revise_no_go(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    result = score_sealed_run(
        sealed_path,
        gold_path,
        public_inputs=paths,
        scorer=lambda *_: _score(
            gate_statuses={"artifact": "PASS", "cross_paper": "PASS", "human_gold": "BLOCKED"}
        ),
    )
    assert result["status"] == "SCORED"
    assert result["overall_decision"] == "REVISE"
    assert result["p0_release"] == "NO-GO"


def test_valid_score_with_nonzero_critical_metric_is_no_go(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    result = score_sealed_run(
        sealed_path,
        gold_path,
        public_inputs=paths,
        scorer=lambda *_: _score(critical_unsupported_claims=1),
    )
    assert result["overall_decision"] == "REVISE"
    assert result["p0_release"] == "NO-GO"


def test_locator_source_hash_and_active_object_are_fail_closed(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    inventory_path = tmp_path / "active-locators.json"
    inventory_path.write_text(
        json.dumps(
            {
                "papers": [
                    {
                        "blind_id": "P01",
                        "label_candidates": [
                            {
                                "blind_id": "P01",
                                "paper_id": "P01",
                                "version_id": "v1",
                                "object_id": "object-1",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    paths = replace(paths, active_locator_inventory=inventory_path)
    rows = _gold_rows()
    rows[0]["evidence_locators"] = [
        {
            "schema_version": "academic.v1",
            "paper_id": "P01",
            "version_id": "v1",
            "object_id": "object-1",
            "page_number": 1,
            "object_type": "paragraph",
            "source_hash": "01" * 32,
        }
    ]
    _write_jsonl(gold_path, rows)
    score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())

    rows[0]["evidence_locators"][0]["source_hash"] = "02" * 32
    _write_jsonl(gold_path, rows)
    with pytest.raises(P0SealedRunError, match="source hash"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())


def test_fake_resealed_envelope_with_changed_public_digest_cannot_score(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    _rewrite_sealed(
        sealed_path,
        lambda payload: payload["public_input_digests"].update({"frozen_set": "0" * 64}),
    )
    with pytest.raises(P0SealedRunError, match="public-input digests"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())


def test_protocol_version_and_question_ids_are_seal_blockers(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    _rewrite_sealed(sealed_path, lambda payload: payload.update({"protocol_version": "wrong.v1"}))
    with pytest.raises(P0SealedRunError, match="protocol version"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())

    paths, sealed_path, gold_path = _sealed_fixture(tmp_path / "ids")
    _rewrite_sealed(
        sealed_path,
        lambda payload: payload.update(
            {"question_ids": [f"X{index:02d}" for index in range(1, 33)]}
        ),
    )
    with pytest.raises(P0SealedRunError, match="question IDs"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())


def test_mutating_questions_or_frozen_set_after_seal_blocks_score(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    paths.questions.write_text(
        paths.questions.read_text(encoding="utf-8").replace("Human verified question 1", "changed"),
        encoding="utf-8",
    )
    with pytest.raises(P0SealedRunError, match="digest mismatch"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())

    paths, sealed_path, gold_path = _sealed_fixture(tmp_path / "frozen")
    paths.frozen_set.write_text(
        paths.frozen_set.read_text(encoding="utf-8").replace("fixture", "changed"), encoding="utf-8"
    )
    with pytest.raises(P0SealedRunError, match="digest mismatch"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())


def test_load_sealed_run_rejects_non_q_question_ids(tmp_path: Path) -> None:
    paths, sealed_path, _ = _sealed_fixture(tmp_path)
    _rewrite_sealed(
        sealed_path,
        lambda payload: payload.update(
            {"question_ids": [f"X{index:02d}" for index in range(1, 33)]}
        ),
    )
    with pytest.raises(P0SealedRunError, match="question IDs"):
        load_sealed_run(sealed_path)
    assert paths.questions.is_file()


@pytest.mark.parametrize(
    "bad_score",
    [
        {},
        {"question_count": 32},
        {"question_count": 32, "false_go": "0"},
        {"question_count": 32, "scored_question_ids": [f"Q{index:02d}" for index in range(1, 32)]},
        {
            "question_count": 32,
            "scored_question_ids": [f"Q{index:02d}" for index in range(1, 33)] + ["Q32"],
        },
        {
            "question_count": 32,
            "scored_question_ids": [f"Q{index:02d}" for index in range(1, 33)],
            "false_go": -1,
        },
    ],
)
def test_invalid_scientific_scorer_output_is_blocked(
    tmp_path: Path, bad_score: dict[str, object]
) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    result = score_sealed_run(
        sealed_path,
        gold_path,
        public_inputs=paths,
        scorer=lambda *_: bad_score,
    )
    assert result["status"] == "BLOCKED"


def test_scorer_error_and_missing_scorer_are_blocked(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)

    def broken(*_: object) -> dict[str, object]:
        raise RuntimeError("scorer unavailable")

    assert (
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=broken)["status"]
        == "BLOCKED"
    )
    assert score_sealed_run(sealed_path, gold_path, public_inputs=paths)["status"] == "BLOCKED"


def test_strict_human_gold_rejects_ai_draft_and_invalid_fields(tmp_path: Path) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    rows = _gold_rows()
    rows[0]["accepted_answers"] = []
    rows[1]["should_abstain"] = "false"
    rows[2]["evidence_locators"] = ["not-a-locator"]
    rows[3]["reviewer_id"] = rows[3]["annotator_id"]
    rows[4]["disagreement_resolution"] = ""
    rows[5]["supporting_paper_ids"] = ["P99"]
    rows[6]["draft_status"] = "AI_DRAFT_NOT_HUMAN_ANNOTATION"
    _write_jsonl(gold_path, rows)
    with pytest.raises(P0SealedRunError, match=r"human gold schema|accepted answer|boolean|paper"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())


def test_placeholder_pack_passes_integrity_but_is_not_run_ready(tmp_path: Path) -> None:
    paths, _ = _public_fixture(tmp_path)
    rows = paths.questions.read_text(encoding="utf-8").replace(
        "Human verified question 1", "HUMAN_AUTHOR_REQUIRED"
    )
    paths.questions.write_text(rows, encoding="utf-8")
    protocol = json.loads(paths.protocol.read_text(encoding="utf-8"))
    protocol["question_pack"] = dict(protocol["question_pack"])
    protocol["question_pack"]["sha256"] = _digest(paths.questions)
    paths.protocol.write_text(json.dumps(protocol), encoding="utf-8")
    validate_public_inputs(paths)
    with pytest.raises(P0SealedRunError, match="HUMAN_QUESTION_AUTHORING"):
        validate_scientific_run_readiness(paths)


def test_gold_loader_is_not_reached_when_public_digest_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, sealed_path, gold_path = _sealed_fixture(tmp_path)
    called = False

    def fail_if_called(*_: object, **__: object) -> tuple[dict[str, object], ...]:
        nonlocal called
        called = True
        raise AssertionError("gold loader reached before public validation")

    monkeypatch.setattr(sealed_module, "_load_human_gold_after_seal", fail_if_called)
    paths.frozen_set.write_text(
        paths.frozen_set.read_text(encoding="utf-8").replace("fixture", "mutated"), encoding="utf-8"
    )
    with pytest.raises(P0SealedRunError, match="digest mismatch"):
        score_sealed_run(sealed_path, gold_path, public_inputs=paths, scorer=lambda *_: _score())
    assert called is False
