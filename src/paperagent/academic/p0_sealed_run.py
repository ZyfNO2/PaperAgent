"""Fail-closed Academic RAG P0 public-input and sealed-run boundary.

The public phase validates only committed resources.  It never receives a gold
path or gold payload.  A sealed run records raw-byte digests of every public
input; scoring revalidates those same paths before it opens human gold.

This API boundary is not process-level blind isolation: it does not prevent a
caller with filesystem access from reading a private gold file.  A production
runner must place the answerer in an isolated process/container and report
``BLOCKED_BY_PROCESS_LEVEL_BLIND_ISOLATION`` until that control exists.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import TypedDict, cast

from paperagent.academic.p0_acceptance import (
    P0_PROTOCOL_VERSION,
    P0AcceptanceError,
    Status,
    canonical_sha256,
    decide_p0,
    load_protocol,
    verify_file_digest,
)

P0_BLINDED_QUESTION_SCHEMA = "academic-rag-p0-blinded-question.v1"
P0_GOLD_SCHEMA = "academic-rag-p0-gold-label.v1"
P0_SEALED_RUN_SCHEMA = "academic-rag-p0-sealed-run.v1"
P0_POST_SEAL_SCORE_SCHEMA = "academic-rag-p0-post-seal-score.v1"
P0_QUESTION_TYPES = ("text", "figure", "table", "equation")
P0_QUESTION_COUNT = 32
P0_DISTRIBUTION = {question_type: 8 for question_type in P0_QUESTION_TYPES}
_GATE_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
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
    "gold_path",
    "accepted_answers",
    "annotator_id",
    "reviewer_id",
    "disagreement_resolution",
}
_HUMAN_GOLD_FIELDS = {
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
_FROZEN_PAPER_IDS = {f"P{index:02d}" for index in range(1, 13)}
_EXPECTED_QUESTION_IDS = tuple(f"Q{index:02d}" for index in range(1, 33))


class ScientificP0Score(TypedDict):
    """Complete scorer output required before a P0 decision is made."""

    question_count: int
    scored_question_ids: list[str]
    critical_unsupported_claims: int
    major_unsupported_claims: int
    critical_citation_mismatches: int
    major_citation_mismatches: int
    false_go: int
    abstention_correct: int
    abstention_incorrect: int
    answerable_correct: int
    answerable_incorrect: int
    artifact_gate_status: str
    cross_paper_gate_status: str
    gate_statuses: dict[str, str]
    denominator_status: str


ScientificP0Scorer = Callable[
    [tuple[dict[str, object], ...], tuple[dict[str, object], ...]],
    Mapping[str, object],
]


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
    frozen_set: Path
    active_locator_inventory: Path | None = None


@dataclass(frozen=True)
class ValidatedP0PublicInputs:
    protocol: dict[str, object]
    questions: tuple[dict[str, object], ...]
    digests: dict[str, str]
    frozen_papers: dict[str, dict[str, object]]
    corpus_entries: dict[str, dict[str, object]]


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
    if not isinstance(value, str) or not value.strip():
        raise P0SealedRunError(f"{description} must be a non-empty string")
    return value


def _verify_public_digest(path: Path, expected: str) -> str:
    try:
        return verify_file_digest(path, expected)
    except (OSError, P0AcceptanceError) as exc:
        raise P0SealedRunError(str(exc)) from exc


def _validate_blinded_questions(
    path: Path,
    *,
    require_human_authoring: bool,
) -> tuple[dict[str, object], ...]:
    rows = _read_jsonl(path)
    if len(rows) != P0_QUESTION_COUNT:
        raise P0SealedRunError("P0 blinded benchmark must contain exactly 32 questions")
    ids = tuple(_string(row.get("question_id"), "question_id") for row in rows)
    if ids != _EXPECTED_QUESTION_IDS:
        raise P0SealedRunError("P0 question IDs must be exactly Q01-Q32 in order")
    for row in rows:
        question_id = _string(row.get("question_id"), "question_id")
        if set(row) != _BLINDED_FIELDS:
            raise P0SealedRunError(f"question {question_id} contains non-public fields")
        if row.get("schema_version") != P0_BLINDED_QUESTION_SCHEMA:
            raise P0SealedRunError("unsupported P0 blinded question schema")
        if row.get("blind") is not True:
            raise P0SealedRunError(f"question {question_id} is not blind")
        if row.get("question_type") not in P0_QUESTION_TYPES:
            raise P0SealedRunError(f"invalid question type for {question_id}")
        question = row.get("question")
        if not isinstance(question, str) or not question.strip():
            raise P0SealedRunError(f"question {question_id} has no text")
        if require_human_authoring and (
            question in {"HUMAN_AUTHOR_REQUIRED", "HUMAN_FILL"}
            or row.get("authoring_status") not in {"human_verified", "ready"}
        ):
            raise P0SealedRunError("scientific run is BLOCKED_BY_HUMAN_QUESTION_AUTHORING")
    distribution = {
        question_type: sum(row["question_type"] == question_type for row in rows)
        for question_type in P0_QUESTION_TYPES
    }
    if distribution != P0_DISTRIBUTION:
        raise P0SealedRunError(f"invalid P0 question distribution: {distribution}")
    return rows


def _validate_manifest(
    path: Path,
    expected_count: int | None,
) -> dict[str, dict[str, object]]:
    rows = _read_jsonl(path)
    if expected_count is not None and len(rows) != expected_count:
        raise P0SealedRunError(
            f"corpus manifest count mismatch: expected {expected_count}, got {len(rows)}"
        )
    entries: dict[str, dict[str, object]] = {}
    for row in rows:
        entry_id = _string(row.get("entry_id"), "corpus.entry_id")
        if entry_id in entries:
            raise P0SealedRunError("corpus manifest contains duplicate entry_id values")
        _string(row.get("file_sha256"), f"corpus.{entry_id}.file_sha256")
        entries[entry_id] = row
    return entries


def _validate_frozen_set(
    path: Path,
    *,
    protocol: Mapping[str, object],
    corpus_entries: Mapping[str, dict[str, object]],
    corpus_digest: str,
) -> dict[str, dict[str, object]]:
    frozen_spec = _mapping(protocol.get("frozen_set"), "protocol.frozen_set")
    frozen_digest = _string(frozen_spec.get("sha256"), "frozen_set.sha256")
    _verify_public_digest(path, frozen_digest)
    if frozen_spec.get("path") != "benchmarks/academic_rag/v1/frozen_12.json":
        raise P0SealedRunError("protocol frozen_set path is not the frozen H0 set")
    if frozen_spec.get("frozen_set_id") != "academic-rag-h0-v1":
        raise P0SealedRunError("unsupported frozen set ID")
    if frozen_spec.get("count") != 12:
        raise P0SealedRunError("frozen set count is not exactly 12")

    frozen = _read_json(path)
    if frozen.get("schema_version") != "academic-frozen-set.v1":
        raise P0SealedRunError("unsupported frozen set schema")
    if frozen.get("frozen_set_id") != frozen_spec.get("frozen_set_id"):
        raise P0SealedRunError("frozen set ID disagrees with protocol")
    if frozen.get("manifest_sha256") != corpus_digest:
        raise P0SealedRunError("frozen set manifest digest disagrees with corpus")
    papers_value = frozen.get("papers")
    if not isinstance(papers_value, list) or len(papers_value) != 12:
        raise P0SealedRunError("frozen set must contain exactly 12 papers")
    papers: dict[str, dict[str, object]] = {}
    frozen_entry_ids: set[str] = set()
    observed_strata: dict[str, int] = {}
    for value in papers_value:
        if not isinstance(value, dict):
            raise P0SealedRunError("frozen set paper entry must be an object")
        paper_id = _string(value.get("blind_id"), "frozen.blind_id")
        entry_id = _string(value.get("entry_id"), f"frozen.{paper_id}.entry_id")
        file_sha256 = _string(value.get("file_sha256"), f"frozen.{paper_id}.file_sha256")
        stratum = _string(value.get("benchmark_stratum"), f"frozen.{paper_id}.stratum")
        if paper_id not in _FROZEN_PAPER_IDS or paper_id in papers or entry_id in frozen_entry_ids:
            raise P0SealedRunError("frozen set IDs must be unique P01-P12")
        corpus_row = corpus_entries.get(entry_id)
        if corpus_row is None:
            raise P0SealedRunError(f"frozen entry {entry_id} is absent from corpus manifest")
        if corpus_row.get("file_sha256") != file_sha256:
            raise P0SealedRunError(f"frozen/corpus source hash mismatch for {paper_id}")
        papers[paper_id] = value
        frozen_entry_ids.add(entry_id)
        observed_strata[stratum] = observed_strata.get(stratum, 0) + 1
    if set(papers) != _FROZEN_PAPER_IDS:
        raise P0SealedRunError("frozen set IDs must be complete P01-P12")
    expected_strata = frozen.get("stratum_counts")
    if not isinstance(expected_strata, dict) or observed_strata != expected_strata:
        raise P0SealedRunError("frozen set stratum counts are invalid")
    return papers


def validate_frozen_resource_integrity(paths: P0PublicInputPaths) -> ValidatedP0PublicInputs:
    """Validate committed resource identity, allowing question authoring placeholders."""

    protocol = load_protocol(paths.protocol)
    contract_files = _mapping(protocol.get("contract_files"), "protocol.contract_files")
    for name, path in (("schema", paths.schema), ("golden", paths.golden_fixture)):
        resource = _mapping(contract_files.get(name), f"contract_files.{name}")
        _verify_public_digest(path, _string(resource.get("sha256"), f"{name}.sha256"))
    schema_contract = _mapping(contract_files.get("schema"), "contract_files.schema")
    golden_contract = _mapping(contract_files.get("golden"), "contract_files.golden")
    if protocol.get("schema_digest") != schema_contract.get("sha256"):
        raise P0SealedRunError("protocol schema digest disagrees with contract file")
    if protocol.get("golden_fixture_digest") != golden_contract.get("sha256"):
        raise P0SealedRunError("protocol golden digest disagrees with contract file")

    question_pack = _mapping(protocol.get("question_pack"), "protocol.question_pack")
    if question_pack.get("path") not in (
        None,
        "benchmarks/academic_rag/v1/eval/questions.blinded.jsonl",
    ):
        raise P0SealedRunError("protocol question pack path is not the frozen blinded pack")
    questions_digest = _string(question_pack.get("sha256"), "question_pack.sha256")
    question_manifest_digest = _string(
        question_pack.get("question_manifest_sha256"),
        "question_pack.question_manifest_sha256",
    )
    artifact_digest = _string(
        question_pack.get("artifact_manifest_sha256"),
        "question_pack.artifact_manifest_sha256",
    )
    _verify_public_digest(paths.questions, questions_digest)
    _verify_public_digest(paths.question_manifest, question_manifest_digest)
    _verify_public_digest(paths.artifact_manifest, artifact_digest)
    corpus_digest = _string(protocol.get("corpus_manifest_sha256"), "corpus_manifest_sha256")
    _verify_public_digest(paths.corpus_manifest, corpus_digest)
    manifest_count = protocol.get("corpus_manifest_entry_count")
    expected_count = (
        manifest_count
        if isinstance(manifest_count, int) and not isinstance(manifest_count, bool)
        else None
    )
    corpus_entries = _validate_manifest(paths.corpus_manifest, expected_count)
    frozen_papers = _validate_frozen_set(
        paths.frozen_set,
        protocol=protocol,
        corpus_entries=corpus_entries,
        corpus_digest=corpus_digest,
    )

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
    questions = _validate_blinded_questions(paths.questions, require_human_authoring=False)
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
            "frozen_set": canonical_sha256(paths.frozen_set),
        },
        frozen_papers=frozen_papers,
        corpus_entries=corpus_entries,
    )


def validate_public_inputs(paths: P0PublicInputPaths) -> ValidatedP0PublicInputs:
    """Compatibility name for the PASS-only frozen resource integrity phase."""

    return validate_frozen_resource_integrity(paths)


def validate_scientific_run_readiness(
    paths: P0PublicInputPaths,
) -> ValidatedP0PublicInputs:
    """Require human-authored questions after public resource integrity passes."""

    validated = validate_frozen_resource_integrity(paths)
    _validate_blinded_questions(paths.questions, require_human_authoring=True)
    return validated


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
    """Run human-authored questions and write one immutable sealed envelope."""

    if not run_id.strip():
        raise P0SealedRunError("run_id must be non-empty")
    if output_path.exists():
        raise P0SealedRunError(f"refusing to overwrite sealed run: {output_path}")
    validated = validate_scientific_run_readiness(paths)
    responses: list[dict[str, object]] = []
    for question in validated.questions:
        answer = answerer(question)
        if not isinstance(answer, Mapping):
            raise P0SealedRunError(f"answer for {question['question_id']} is not an object")
        _reject_private_gold(answer)
        required = {"response", "citations", "contexts", "trace"}
        if not required <= set(answer):
            raise P0SealedRunError(
                f"answer for {question['question_id']} is missing sealed fields: "
                f"{sorted(required - set(answer))}"
            )
        responses.append({"question_id": question["question_id"], **dict(answer)})
    envelope: dict[str, object] = {
        "schema_version": P0_SEALED_RUN_SCHEMA,
        "protocol_version": P0_PROTOCOL_VERSION,
        "run_id": run_id,
        "sealed_at_utc": sealed_at_utc or _utc_now(),
        "question_count": P0_QUESTION_COUNT,
        "question_ids": list(_EXPECTED_QUESTION_IDS),
        "public_input_digests": validated.digests,
        "responses": responses,
    }
    sealed = {**envelope, "run_digest": _run_digest(envelope)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as stream:
            stream.write(_canonical_bytes(sealed))
    except FileExistsError as exc:
        raise P0SealedRunError(f"refusing to overwrite sealed run: {output_path}") from exc
    return sealed


def load_sealed_run(path: Path) -> dict[str, object]:
    """Validate envelope integrity and require exactly Q01-Q32."""

    payload = _read_json(path)
    if payload.get("schema_version") != P0_SEALED_RUN_SCHEMA:
        raise P0SealedRunError("unsupported sealed-run schema")
    if payload.get("protocol_version") != P0_PROTOCOL_VERSION:
        raise P0SealedRunError("sealed run protocol version mismatch")
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
    if question_ids != list(_EXPECTED_QUESTION_IDS):
        raise P0SealedRunError("sealed run question IDs must be exactly Q01-Q32")
    if len(responses) != P0_QUESTION_COUNT:
        raise P0SealedRunError("sealed run denominator is not exactly 32")
    response_ids: list[object] = []
    for row in responses:
        if not isinstance(row, dict):
            raise P0SealedRunError("sealed run response rows must be objects")
        response_ids.append(row.get("question_id"))
        _reject_private_gold(row)
    if response_ids != question_ids:
        raise P0SealedRunError("sealed response IDs do not match Q01-Q32")
    return payload


def _load_active_locator_keys(
    path: Path | None,
) -> frozenset[tuple[str, str, str]] | None:
    if path is None:
        return None
    inventory = _read_json(path)
    papers = inventory.get("papers")
    if not isinstance(papers, list):
        raise P0SealedRunError("active locator inventory.papers must be a list")
    keys: set[tuple[str, str, str]] = set()
    for paper in papers:
        if not isinstance(paper, dict):
            raise P0SealedRunError("active locator inventory paper must be an object")
        aliases = {paper.get("blind_id"), paper.get("paper_id")}
        candidates = paper.get("label_candidates")
        if not isinstance(candidates, list):
            raise P0SealedRunError("active locator inventory candidates must be a list")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise P0SealedRunError("active locator candidate must be an object")
            candidate_aliases = aliases | {candidate.get("blind_id"), candidate.get("paper_id")}
            version_id = candidate.get("version_id")
            object_id = candidate.get("object_id")
            if not isinstance(version_id, str) or not isinstance(object_id, str):
                raise P0SealedRunError("active locator candidate identity is invalid")
            for alias in candidate_aliases:
                if isinstance(alias, str) and alias:
                    keys.add((alias, version_id, object_id))
    return frozenset(keys)


def _string_list(value: object, description: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise P0SealedRunError(f"{description} must be a list of non-empty strings")
    if nonempty and not value:
        raise P0SealedRunError(f"{description} must not be empty")
    return value


def _validate_evidence_locator(
    raw: object,
    *,
    supporting_paper_ids: set[str],
    frozen_papers: Mapping[str, dict[str, object]],
    active_locator_keys: frozenset[tuple[str, str, str]] | None,
) -> None:
    if not isinstance(raw, Mapping):
        raise P0SealedRunError("evidence_locators entries must be objects")
    paper_id = _string(raw.get("paper_id"), "evidence_locator.paper_id")
    version_id = _string(raw.get("version_id"), "evidence_locator.version_id")
    object_id = _string(raw.get("object_id"), "evidence_locator.object_id")
    object_type = _string(raw.get("object_type"), "evidence_locator.object_type")
    source_hash = _string(raw.get("source_hash"), "evidence_locator.source_hash")
    if paper_id not in supporting_paper_ids or paper_id not in frozen_papers:
        raise P0SealedRunError("supporting paper does not match evidence locator paper")
    expected_hash = frozen_papers[paper_id].get("file_sha256")
    if source_hash != expected_hash:
        raise P0SealedRunError("evidence locator source hash is stale or belongs to another paper")
    if raw.get("schema_version") != "academic.v1":
        raise P0SealedRunError("unsupported EvidenceLocator schema")
    page_number = raw.get("page_number")
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        raise P0SealedRunError("evidence locator page_number is invalid")
    if object_type not in {
        "document",
        "page",
        "section",
        "paragraph",
        "figure",
        "caption",
        "table",
        "table_cell",
        "equation",
        "algorithm",
        "reference",
    }:
        raise P0SealedRunError("evidence locator object_type is invalid")
    if active_locator_keys is None:
        raise P0SealedRunError("active locator inventory is required for non-abstention gold")
    if (paper_id, version_id, object_id) not in active_locator_keys:
        raise P0SealedRunError("evidence locator is stale or references an inactive object")
    try:
        locator_module = import_module("paperclaw.academic.contracts")
        locator_type = locator_module.EvidenceLocator
        locator_type.from_dict(dict(raw))
    except ModuleNotFoundError:
        # PaperAgent has an optional PaperClaw dependency; the checks above
        # mirror EvidenceLocator.from_dict when the optional package is absent.
        pass
    except (KeyError, TypeError, ValueError) as exc:
        raise P0SealedRunError("evidence locator failed EvidenceLocator validation") from exc


def _load_human_gold_after_seal(
    path: Path,
    validated: ValidatedP0PublicInputs,
    *,
    active_locator_keys: frozenset[tuple[str, str, str]] | None,
) -> tuple[dict[str, object], ...]:
    rows = _read_jsonl(path)
    if len(rows) != P0_QUESTION_COUNT:
        raise P0SealedRunError("human gold must contain exactly 32 labels")
    seen: set[str] = set()
    for row in rows:
        question_id = _string(row.get("question_id"), "gold.question_id")
        if question_id not in _EXPECTED_QUESTION_IDS or question_id in seen:
            raise P0SealedRunError("human gold question IDs must be exact and unique")
        seen.add(question_id)
        if set(row) != _HUMAN_GOLD_FIELDS or row.get("schema_version") != P0_GOLD_SCHEMA:
            raise P0SealedRunError(
                f"human gold schema is invalid for {question_id}; AI drafts are ineligible"
            )
        accepted_answers = _string_list(row.get("accepted_answers"), "gold.accepted_answers")
        supporting_paper_ids = _string_list(
            row.get("supporting_paper_ids"), "gold.supporting_paper_ids"
        )
        if any(paper_id not in _FROZEN_PAPER_IDS for paper_id in supporting_paper_ids):
            raise P0SealedRunError("human gold supporting paper is outside frozen P01-P12")
        locators = row.get("evidence_locators")
        if not isinstance(locators, list):
            raise P0SealedRunError("gold.evidence_locators must be a list")
        should_abstain = row.get("should_abstain")
        if not isinstance(should_abstain, bool):
            raise P0SealedRunError("gold.should_abstain must be a boolean")
        if should_abstain and (accepted_answers or supporting_paper_ids or locators):
            raise P0SealedRunError("abstention gold cannot contain answers, papers, or locators")
        if not should_abstain and not accepted_answers:
            raise P0SealedRunError("non-abstention gold requires an accepted answer")
        _string_list(row.get("allowable_inference"), "gold.allowable_inference")
        _string_list(row.get("forbidden_overclaim"), "gold.forbidden_overclaim", nonempty=True)
        _string_list(
            row.get("severe_error_conditions"),
            "gold.severe_error_conditions",
            nonempty=True,
        )
        annotator_id = _string(row.get("annotator_id"), "gold.annotator_id")
        reviewer_id = _string(row.get("reviewer_id"), "gold.reviewer_id")
        if annotator_id == reviewer_id:
            raise P0SealedRunError("annotator_id and reviewer_id must be different humans")
        annotated_at = _string(row.get("annotated_at"), "gold.annotated_at")
        try:
            datetime.fromisoformat(annotated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise P0SealedRunError("gold.annotated_at is not valid ISO8601") from exc
        disagreement = row.get("disagreement_resolution")
        if not (
            (isinstance(disagreement, str) and disagreement.strip())
            or (isinstance(disagreement, Mapping) and bool(disagreement))
        ):
            raise P0SealedRunError("gold.disagreement_resolution must be non-empty")
        for locator in locators:
            _validate_evidence_locator(
                locator,
                supporting_paper_ids=set(supporting_paper_ids),
                frozen_papers=validated.frozen_papers,
                active_locator_keys=active_locator_keys,
            )
    if seen != set(_EXPECTED_QUESTION_IDS):
        raise P0SealedRunError("human gold is missing one or more question IDs")
    return rows


_SCORE_INT_FIELDS = (
    "question_count",
    "critical_unsupported_claims",
    "major_unsupported_claims",
    "critical_citation_mismatches",
    "major_citation_mismatches",
    "false_go",
    "abstention_correct",
    "abstention_incorrect",
    "answerable_correct",
    "answerable_incorrect",
)
_SCORE_REQUIRED_FIELDS = set(_SCORE_INT_FIELDS) | {
    "scored_question_ids",
    "artifact_gate_status",
    "cross_paper_gate_status",
    "gate_statuses",
    "denominator_status",
}


def _validate_scientific_score(value: Mapping[str, object]) -> ScientificP0Score:
    if set(value) != _SCORE_REQUIRED_FIELDS:
        raise P0SealedRunError("scientific scorer output does not match the complete P0 schema")
    for field in _SCORE_INT_FIELDS:
        metric = value.get(field)
        if isinstance(metric, bool) or not isinstance(metric, int) or metric < 0:
            raise P0SealedRunError(f"scientific score metric {field} must be non-negative int")
    if value.get("question_count") != P0_QUESTION_COUNT:
        raise P0SealedRunError("scientific score question_count must be exactly 32")
    ids = value.get("scored_question_ids")
    if ids != list(_EXPECTED_QUESTION_IDS):
        raise P0SealedRunError("scientific score IDs must be exactly Q01-Q32")
    for field in ("artifact_gate_status", "cross_paper_gate_status"):
        if value.get(field) not in _GATE_STATUSES:
            raise P0SealedRunError(f"unknown {field}")
    gates = value.get("gate_statuses")
    if not isinstance(gates, dict) or not gates:
        raise P0SealedRunError("scientific score gate_statuses must be non-empty")
    for gate_id, status in gates.items():
        if (
            not isinstance(gate_id, str)
            or not isinstance(status, str)
            or status not in _GATE_STATUSES
        ):
            raise P0SealedRunError("scientific score contains an unknown gate status")
    if gates.get("artifact") != value["artifact_gate_status"]:
        raise P0SealedRunError("artifact gate status is not bound to gate_statuses")
    if gates.get("cross_paper") != value["cross_paper_gate_status"]:
        raise P0SealedRunError("cross-paper gate status is not bound to gate_statuses")
    if value.get("denominator_status") != "EXACT_FROZEN_32":
        raise P0SealedRunError("scientific score denominator is not exact frozen 32")
    return cast(ScientificP0Score, dict(value))


def _blocked_score_result(
    sealed: Mapping[str, object],
    human_gold_path: Path,
    reason: str,
) -> dict[str, object]:
    return {
        "schema_version": P0_POST_SEAL_SCORE_SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "run_digest": sealed["run_digest"],
        "gold_digest": canonical_sha256(human_gold_path) if human_gold_path.is_file() else None,
        "process_blind_isolation_status": "BLOCKED_BY_PROCESS_LEVEL_BLIND_ISOLATION",
    }


def score_sealed_run(
    sealed_run_path: Path,
    human_gold_path: Path,
    *,
    public_inputs: P0PublicInputPaths,
    scorer: ScientificP0Scorer | None = None,
) -> dict[str, object]:
    """Revalidate public inputs and seal bindings before opening human gold."""

    sealed = load_sealed_run(sealed_run_path)
    validated = validate_public_inputs(public_inputs)
    sealed_digests = sealed.get("public_input_digests")
    if not isinstance(sealed_digests, dict) or sealed_digests != validated.digests:
        raise P0SealedRunError("sealed run public-input digests do not match current resources")
    if sealed.get("protocol_version") != validated.protocol.get("protocol_version"):
        raise P0SealedRunError("sealed run protocol version does not match current protocol")
    if sealed.get("question_ids") != list(_EXPECTED_QUESTION_IDS):
        raise P0SealedRunError("sealed run question IDs do not match current Q01-Q32 pack")
    validate_scientific_run_readiness(public_inputs)
    if scorer is None:
        return _blocked_score_result(
            sealed,
            human_gold_path,
            "a complete scientific post-seal scorer was not supplied",
        )
    active_locator_keys = _load_active_locator_keys(public_inputs.active_locator_inventory)
    gold = _load_human_gold_after_seal(
        human_gold_path,
        validated,
        active_locator_keys=active_locator_keys,
    )
    response_payload = sealed.get("responses")
    if not isinstance(response_payload, list):
        raise P0SealedRunError("sealed run responses must be a list")
    responses = tuple(row for row in response_payload if isinstance(row, dict))
    try:
        raw_score = scorer(responses, gold)
        if not isinstance(raw_score, Mapping):
            raise P0SealedRunError("scientific scorer did not return an object")
        score = _validate_scientific_score(raw_score)
    except Exception as exc:
        return _blocked_score_result(sealed, human_gold_path, f"scientific scorer blocked: {exc}")
    gate_statuses: dict[str, Status] = {
        str(gate_id): cast(Status, status) for gate_id, status in score["gate_statuses"].items()
    }
    decision = decide_p0(
        "GO",
        gate_statuses,
        critical_unsupported_claims=score["critical_unsupported_claims"],
        critical_citation_mismatches=score["critical_citation_mismatches"],
        false_go=score["false_go"],
    )
    return {
        "schema_version": P0_POST_SEAL_SCORE_SCHEMA,
        "status": "SCORED",
        "run_digest": sealed["run_digest"],
        "gold_digest": canonical_sha256(human_gold_path),
        "scores": score,
        **decision,
        "artifact_gate_status": score["artifact_gate_status"],
        "cross_paper_gate_status": score["cross_paper_gate_status"],
        "process_blind_isolation_status": "BLOCKED_BY_PROCESS_LEVEL_BLIND_ISOLATION",
    }


__all__ = [
    "P0_BLINDED_QUESTION_SCHEMA",
    "P0_DISTRIBUTION",
    "P0_GOLD_SCHEMA",
    "P0_POST_SEAL_SCORE_SCHEMA",
    "P0_SEALED_RUN_SCHEMA",
    "P0PublicInputPaths",
    "P0SealedRunError",
    "ScientificP0Score",
    "ScientificP0Scorer",
    "ValidatedP0PublicInputs",
    "load_sealed_run",
    "run_p0_blinded",
    "score_sealed_run",
    "validate_frozen_resource_integrity",
    "validate_public_inputs",
    "validate_scientific_run_readiness",
]
