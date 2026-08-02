"""Cross-repository Academic RAG P0 sealed-run lifecycle.

The public phase accepts only the frozen protocol, contract digests, corpus
manifest, artifact manifest, question manifest, and blinded questions.  Gold
labels are intentionally absent from every public-phase function signature.
They become readable only through :func:`score_sealed_run`, after an
immutable run envelope and digest have been written successfully.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from paperagent.academic.p0_acceptance import (
    P0_PROTOCOL_VERSION,
    P0AcceptanceError,
    canonical_sha256,
    load_protocol,
    verify_file_digest,
)

P0_BLINDED_QUESTION_SCHEMA = "academic-rag-p0-blinded-question.v1"
P0_SEALED_RUN_SCHEMA = "academic-rag-p0-sealed-run.v1"
P0_POST_SEAL_SCORE_SCHEMA = "academic-rag-p0-post-seal-score.v1"
P0_QUESTION_TYPES = ("text", "figure", "table", "equation")
P0_QUESTION_COUNT = 32
P0_DISTRIBUTION = {question_type: 8 for question_type in P0_QUESTION_TYPES}
_BLINDED_FIELDS = {
    "schema_version",
    "question_id",
    "question_type",
    "question",
    "corpus_id",
    "blind",
    "authoring_status",
}
_GOLD_FIELDS = {
    "gold",
    "gold_label",
    "gold_labels",
    "gold_locator",
    "accepted_answers",
    "annotator_id",
    "reviewer_id",
    "disagreement_resolution",
}


@dataclass(frozen=True)
class P0PublicInputPaths:
    """Explicit cross-repository paths required before a run can start."""

    protocol: Path
    schema: Path
    golden_fixture: Path
    corpus_manifest: Path
    questions: Path
    question_manifest: Path
    artifact_manifest: Path


@dataclass(frozen=True)
class ValidatedP0PublicInputs:
    protocol: dict[str, object]
    questions: tuple[dict[str, object], ...]
    digests: dict[str, str]


class P0SealedRunError(P0AcceptanceError):
    """Raised when a public input, response, seal, or score is unsafe."""


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P0SealedRunError(f"cannot load JSON resource: {path}") from exc
    if not isinstance(payload, dict):
        raise P0SealedRunError(f"JSON resource must be an object: {path}")
    return payload


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise P0SealedRunError(f"cannot load JSONL resource: {path}") from exc
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise P0SealedRunError(f"invalid JSONL row {line_number}: {path}") from exc
        if not isinstance(value, dict):
            raise P0SealedRunError(f"JSONL row {line_number} must be an object: {path}")
        rows.append(value)
    return tuple(rows)


def _mapping(value: object, description: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise P0SealedRunError(f"{description} must be an object")
    return value


def _string(value: object, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise P0SealedRunError(f"{description} must be a non-empty string")
    return value


def _verify_public_digest(path: Path, expected: str) -> str:
    try:
        return verify_file_digest(path, expected)
    except P0AcceptanceError as exc:
        raise P0SealedRunError(str(exc)) from exc


def _validate_blinded_questions(path: Path) -> tuple[dict[str, object], ...]:
    rows = _read_jsonl(path)
    if len(rows) != P0_QUESTION_COUNT:
        raise P0SealedRunError("P0 blinded benchmark must contain exactly 32 questions")
    expected_ids = tuple(f"Q{index:02d}" for index in range(1, P0_QUESTION_COUNT + 1))
    ids = tuple(_string(row.get("question_id"), "question_id") for row in rows)
    if ids != expected_ids or len(set(ids)) != len(ids):
        raise P0SealedRunError("P0 question IDs must be exactly Q01-Q32 in order")
    for row in rows:
        if set(row) != _BLINDED_FIELDS:
            raise P0SealedRunError(
                f"question {row.get('question_id')} contains non-public fields"
            )
        if row.get("schema_version") != P0_BLINDED_QUESTION_SCHEMA:
            raise P0SealedRunError("unsupported P0 blinded question schema")
        if row.get("blind") is not True:
            raise P0SealedRunError(f"question {row['question_id']} is not blind")
        if row.get("question_type") not in P0_QUESTION_TYPES:
            raise P0SealedRunError(f"invalid question type for {row['question_id']}")
        question = row.get("question")
        if not isinstance(question, str) or not question.strip():
            raise P0SealedRunError(f"question {row['question_id']} has no text")
        if question in {"HUMAN_AUTHOR_REQUIRED", "HUMAN_FILL"}:
            raise P0SealedRunError(
                "question authoring is incomplete; scientific run is blocked"
            )
        if row.get("authoring_status") not in {"human_verified", "ready"}:
            raise P0SealedRunError(
                f"question {row['question_id']} is not human-verified"
            )
    distribution = {
        question_type: sum(row["question_type"] == question_type for row in rows)
        for question_type in P0_QUESTION_TYPES
    }
    if distribution != P0_DISTRIBUTION:
        raise P0SealedRunError(f"invalid P0 question distribution: {distribution}")
    return rows


def _validate_manifest(path: Path, expected_count: int | None) -> None:
    rows = _read_jsonl(path)
    if expected_count is not None and len(rows) != expected_count:
        raise P0SealedRunError(
            f"corpus manifest count mismatch: expected {expected_count}, got {len(rows)}"
        )
    entry_ids = [row.get("entry_id") for row in rows]
    if any(not isinstance(entry_id, str) or not entry_id for entry_id in entry_ids):
        raise P0SealedRunError("corpus manifest contains an invalid entry_id")
    if len(set(entry_ids)) != len(entry_ids):
        raise P0SealedRunError("corpus manifest contains duplicate entry_id values")


def validate_public_inputs(paths: P0PublicInputPaths) -> ValidatedP0PublicInputs:
    """Verify all public cross-repository resources before model execution."""

    protocol = load_protocol(paths.protocol)
    if protocol.get("protocol_version") != P0_PROTOCOL_VERSION:
        raise P0SealedRunError("unsupported P0 protocol version")

    contract_files = _mapping(protocol.get("contract_files"), "protocol.contract_files")
    for name, path in (("schema", paths.schema), ("golden", paths.golden_fixture)):
        resource = _mapping(contract_files.get(name), f"contract_files.{name}")
        expected_digest = _string(resource.get("sha256"), f"contract_files.{name}.sha256")
        _verify_public_digest(path, expected_digest)
    schema_contract = _mapping(contract_files.get("schema"), "contract_files.schema")
    golden_contract = _mapping(contract_files.get("golden"), "contract_files.golden")
    if protocol.get("schema_digest") != schema_contract.get("sha256"):
        raise P0SealedRunError("protocol schema digest disagrees with contract file")
    if protocol.get("golden_fixture_digest") != golden_contract.get("sha256"):
        raise P0SealedRunError("protocol golden digest disagrees with contract file")

    question_pack = _mapping(protocol.get("question_pack"), "protocol.question_pack")
    questions_digest = _string(question_pack.get("sha256"), "question_pack.sha256")
    _verify_public_digest(paths.questions, questions_digest)
    question_manifest_digest = _string(
        question_pack.get("question_manifest_sha256"),
        "question_pack.question_manifest_sha256",
    )
    _verify_public_digest(paths.question_manifest, question_manifest_digest)
    artifact_digest = _string(
        question_pack.get("artifact_manifest_sha256"),
        "question_pack.artifact_manifest_sha256",
    )
    _verify_public_digest(paths.artifact_manifest, artifact_digest)
    corpus_digest = _string(protocol.get("corpus_manifest_sha256"), "corpus_manifest_sha256")
    _verify_public_digest(paths.corpus_manifest, corpus_digest)

    question_manifest = _read_json(paths.question_manifest)
    if question_manifest.get("question_file") != paths.questions.name:
        raise P0SealedRunError("question manifest points to a different question file")
    if question_manifest.get("question_count") != P0_QUESTION_COUNT:
        raise P0SealedRunError("question manifest count is not 32")
    if question_manifest.get("distribution") != P0_DISTRIBUTION:
        raise P0SealedRunError("question manifest distribution is not 8/8/8/8")

    artifact_manifest = _read_json(paths.artifact_manifest)
    if artifact_manifest.get("schema_version") != "academic-rag-p0-artifact-manifest.v1":
        raise P0SealedRunError("unsupported Artifact manifest schema")
    required_artifacts = artifact_manifest.get("required_artifact_types")
    if not isinstance(required_artifacts, list) or len(required_artifacts) != 8:
        raise P0SealedRunError("Artifact manifest must declare exactly eight types")
    manifest_count = protocol.get("corpus_manifest_entry_count")
    expected_manifest_count = manifest_count if isinstance(manifest_count, int) else None
    _validate_manifest(paths.corpus_manifest, expected_manifest_count)
    questions = _validate_blinded_questions(paths.questions)
    return ValidatedP0PublicInputs(
        protocol=protocol,
        questions=questions,
        digests={
            "protocol": canonical_sha256(paths.protocol),
            "schema": canonical_sha256(paths.schema),
            "golden_fixture": canonical_sha256(paths.golden_fixture),
            "corpus_manifest": canonical_sha256(paths.corpus_manifest),
            "questions": canonical_sha256(paths.questions),
            "question_manifest": canonical_sha256(paths.question_manifest),
            "artifact_manifest": canonical_sha256(paths.artifact_manifest),
        },
    )


def _reject_private_gold(value: object, location: str = "answer") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in _GOLD_FIELDS:
                raise P0SealedRunError(f"private gold field leaked into {location}: {key}")
            _reject_private_gold(item, f"{location}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_private_gold(item, f"{location}[{index}]")
    elif isinstance(value, str) and "must-not-leak" in value:
        raise P0SealedRunError(f"private gold marker leaked into {location}")


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise P0SealedRunError("run envelope is not JSON serializable") from exc


def _run_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_p0_blinded(
    paths: P0PublicInputPaths,
    *,
    run_id: str,
    output_path: Path,
    answerer: Callable[[Mapping[str, object]], Mapping[str, object]],
    sealed_at_utc: str | None = None,
) -> dict[str, object]:
    """Execute all 32 public questions and write one immutable sealed run.

    The answerer receives only one blinded question at a time.  It must return
    response, citation, context, and trace fields.  No gold path or gold
    payload is accepted by this function.
    """

    if not run_id.strip():
        raise P0SealedRunError("run_id must be non-empty")
    if output_path.exists():
        raise P0SealedRunError(f"refusing to overwrite sealed run: {output_path}")
    validated = validate_public_inputs(paths)
    responses: list[dict[str, object]] = []
    for question in validated.questions:
        answer = answerer(question)
        if not isinstance(answer, Mapping):
            raise P0SealedRunError(f"answer for {question['question_id']} is not an object")
        _reject_private_gold(answer)
        required = {"response", "citations", "contexts", "trace"}
        if not required <= set(answer):
            missing = sorted(required - set(answer))
            raise P0SealedRunError(
                f"answer for {question['question_id']} is missing sealed fields: {missing}"
            )
        row = {"question_id": question["question_id"], **dict(answer)}
        responses.append(row)
    if len(responses) != P0_QUESTION_COUNT:
        raise P0SealedRunError("sealed response count is not exactly 32")
    if [row["question_id"] for row in responses] != [
        question["question_id"] for question in validated.questions
    ]:
        raise P0SealedRunError("sealed response IDs do not match the blinded question order")

    envelope: dict[str, object] = {
        "schema_version": P0_SEALED_RUN_SCHEMA,
        "protocol_version": P0_PROTOCOL_VERSION,
        "run_id": run_id,
        "sealed_at_utc": sealed_at_utc or _utc_now(),
        "question_count": P0_QUESTION_COUNT,
        "question_ids": [question["question_id"] for question in validated.questions],
        "public_input_digests": validated.digests,
        "responses": responses,
    }
    sealed = {**envelope, "run_digest": _run_digest(envelope)}
    payload = _canonical_bytes(sealed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise P0SealedRunError(f"refusing to overwrite sealed run: {output_path}") from exc
    return sealed


def load_sealed_run(path: Path) -> dict[str, object]:
    """Validate the immutable run envelope and its content digest."""

    payload = _read_json(path)
    if payload.get("schema_version") != P0_SEALED_RUN_SCHEMA:
        raise P0SealedRunError("unsupported sealed-run schema")
    if payload.get("question_count") != P0_QUESTION_COUNT:
        raise P0SealedRunError("sealed run question_count is not exactly 32")
    run_digest = _string(payload.get("run_digest"), "run_digest")
    unsigned = {key: value for key, value in payload.items() if key != "run_digest"}
    if _run_digest(unsigned) != run_digest:
        raise P0SealedRunError("sealed run digest mismatch")
    responses = payload.get("responses")
    question_ids = payload.get("question_ids")
    if not isinstance(responses, list) or not isinstance(question_ids, list):
        raise P0SealedRunError("sealed run responses/question_ids must be lists")
    if len(responses) != P0_QUESTION_COUNT or len(question_ids) != P0_QUESTION_COUNT:
        raise P0SealedRunError("sealed run denominator is not exactly 32")
    response_ids = [
        row.get("question_id") for row in responses if isinstance(row, dict)
    ]
    if response_ids != question_ids or len(set(response_ids)) != P0_QUESTION_COUNT:
        raise P0SealedRunError("sealed run question IDs are not exact and unique")
    for row in responses:
        _reject_private_gold(row)
    return payload


def _load_human_gold_after_seal(path: Path) -> tuple[dict[str, object], ...]:
    rows = _read_jsonl(path)
    if len(rows) != P0_QUESTION_COUNT:
        raise P0SealedRunError("human gold must contain exactly 32 labels")
    expected_ids = {f"Q{index:02d}" for index in range(1, P0_QUESTION_COUNT + 1)}
    seen: set[str] = set()
    required = {
        "schema_version",
        "question_id",
        "accepted_answers",
        "supporting_paper_ids",
        "evidence_locators",
        "allowable_inference",
        "forbidden_overclaim",
        "should_abstain",
        "severe_error_conditions",
        "annotator_id",
        "reviewer_id",
        "annotated_at",
        "disagreement_resolution",
    }
    for row in rows:
        question_id = _string(row.get("question_id"), "gold.question_id")
        if question_id not in expected_ids or question_id in seen:
            raise P0SealedRunError("human gold question IDs are not exact and unique")
        seen.add(question_id)
        if set(row) != required or row.get("schema_version") != "academic-rag-p0-gold-label.v1":
            raise P0SealedRunError(f"human gold schema is invalid for {question_id}")
        for field in ("annotator_id", "reviewer_id", "annotated_at"):
            _string(row.get(field), f"gold.{question_id}.{field}")
    if seen != expected_ids:
        raise P0SealedRunError("human gold is missing one or more question IDs")
    return rows


def score_sealed_run(
    sealed_run_path: Path,
    human_gold_path: Path,
    *,
    scorer: Callable[
        [tuple[dict[str, object], ...], tuple[dict[str, object], ...]],
        Mapping[str, object],
    ]
    | None = None,
) -> dict[str, object]:
    """Load gold only after seal validation, then score or remain blocked."""

    sealed = load_sealed_run(sealed_run_path)
    # This is deliberately the first operation that can read the private gold.
    gold = _load_human_gold_after_seal(human_gold_path)
    if scorer is None:
        return {
            "schema_version": P0_POST_SEAL_SCORE_SCHEMA,
            "status": "BLOCKED",
            "reason": "a scientific post-seal scorer was not supplied",
            "run_digest": sealed["run_digest"],
            "gold_digest": canonical_sha256(human_gold_path),
        }
    response_payload = sealed.get("responses")
    if not isinstance(response_payload, list):
        raise P0SealedRunError("sealed run responses must be a list")
    responses = tuple(row for row in response_payload if isinstance(row, dict))
    score = dict(scorer(responses, gold))
    return {
        "schema_version": P0_POST_SEAL_SCORE_SCHEMA,
        "status": "SCORED",
        "run_digest": sealed["run_digest"],
        "gold_digest": canonical_sha256(human_gold_path),
        "scores": score,
    }


__all__ = [
    "P0_BLINDED_QUESTION_SCHEMA",
    "P0_DISTRIBUTION",
    "P0_POST_SEAL_SCORE_SCHEMA",
    "P0_SEALED_RUN_SCHEMA",
    "P0PublicInputPaths",
    "P0SealedRunError",
    "ValidatedP0PublicInputs",
    "load_sealed_run",
    "run_p0_blinded",
    "score_sealed_run",
    "validate_public_inputs",
]
