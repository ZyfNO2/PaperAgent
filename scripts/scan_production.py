from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".json"}
EXCLUDED_PARTS = {".git", ".venv", "build", "dist", "__pycache__", ".mypy_cache", ".pytest_cache"}
RUNTIME_FORBIDDEN_PARAMETERS = {
    "case_id",
    "oracle",
    "metadata",
    "scoring",
    "scorer",
    "metamorphic_group",
    "expected_decision",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _iter_text_files(root: Path, *, excluded_files: set[Path] | None = None) -> list[Path]:
    excluded = {path.resolve() for path in (excluded_files or set())}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() in excluded:
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def _load_private_manifest(path: Path | None) -> tuple[list[str], str | None]:
    if path is None:
        return [], None
    payload = path.read_bytes()
    value: Any = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("private scan manifest must be an object")
    raw = value.get("forbidden_ngrams", [])
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ValueError("forbidden_ngrams must be a list of non-empty strings")
    return [item.strip() for item in raw], _sha256_bytes(payload)


def _runtime_signature_findings(production_root: Path) -> list[dict[str, object]]:
    path = production_root / "src/paperagent/claw_benchmark_runtime.py"
    if not path.exists():
        return [{"code": "RUNTIME_FILE_MISSING", "path": str(path)}]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[dict[str, object]] = []
    target: ast.AsyncFunctionDef | ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == "execute_benchmark_input":
            target = node
            break
    if target is None:
        return [{"code": "INPUT_ONLY_EXECUTOR_MISSING", "path": str(path)}]
    names = {
        argument.arg
        for argument in [*target.args.posonlyargs, *target.args.args, *target.args.kwonlyargs]
    }
    forbidden = sorted(names & RUNTIME_FORBIDDEN_PARAMETERS)
    if forbidden:
        findings.append(
            {
                "code": "SCORER_FIELD_IN_RUNTIME_SIGNATURE",
                "path": str(path.relative_to(production_root)),
                "parameters": forbidden,
            }
        )
    required = {"benchmark_input", "llm", "search", "max_llm_calls", "task_id"}
    missing = sorted(required - names)
    if missing:
        findings.append(
            {
                "code": "RUNTIME_SIGNATURE_INCOMPLETE",
                "path": str(path.relative_to(production_root)),
                "missing": missing,
            }
        )
    return findings


def _pilot_source_findings(production_root: Path) -> list[dict[str, object]]:
    path = production_root / "src/paperagent/claw_benchmark_normalizer.py"
    if not path.exists():
        return [{"code": "PILOT_NORMALIZER_FILE_MISSING", "path": str(path)}]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == (
            "normalize_paperagent_state"
        ):
            target = node
            break
    relative = str(path.relative_to(production_root))
    if target is None:
        return [{"code": "PILOT_NORMALIZER_FUNCTION_MISSING", "path": relative}]

    assignments = []
    for node in ast.walk(target):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(assigned, ast.Name) and assigned.id == "pilot_recommended"
            for assigned in node.targets
        ):
            assignments.append(node.value)
    expected = ast.parse(
        "bool(outcome is not None and outcome.pilot_recommended)",
        mode="eval",
    ).body
    assignment_verified = bool(
        len(assignments) == 1
        and ast.dump(assignments[0], include_attributes=False)
        == ast.dump(expected, include_attributes=False)
    )

    update_verified = False
    for node in ast.walk(target):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "pilot_recommended"
                and isinstance(value, ast.Name)
                and value.id == "pilot_recommended"
            ):
                update_verified = True
                break
        if update_verified:
            break

    if assignment_verified and update_verified:
        return []
    return [
        {
            "code": "PILOT_RECOMMENDATION_SOURCE_UNVERIFIED",
            "path": relative,
            "assignment_verified": assignment_verified,
            "trace_update_verified": update_verified,
        }
    ]


def scan_production(
    production_root: Path,
    *,
    private_manifest: Path | None = None,
) -> dict[str, object]:
    root = production_root.resolve()
    forbidden_ngrams, manifest_sha256 = _load_private_manifest(private_manifest)
    excluded_files = {private_manifest.resolve()} if private_manifest is not None else set()
    files = _iter_text_files(root, excluded_files=excluded_files)
    findings = [
        *_runtime_signature_findings(root),
        *_pilot_source_findings(root),
    ]
    pilot_recommendation_source_verified = not any(
        str(item.get("code", "")).startswith("PILOT_") for item in findings
    )
    file_hashes: dict[str, str] = {}

    for path in files:
        relative = str(path.relative_to(root))
        payload = path.read_bytes()
        file_hashes[relative] = _sha256_bytes(payload)
        if not forbidden_ngrams:
            continue
        text = payload.decode("utf-8", errors="replace").casefold()
        for ngram in forbidden_ngrams:
            normalized = ngram.casefold()
            if normalized in text:
                findings.append(
                    {
                        "code": "PRIVATE_NGRAM_IN_EVALUATED_REPOSITORY",
                        "path": relative,
                        "ngram_sha256": _sha256_bytes(normalized.encode("utf-8")),
                    }
                )

    production_digest = hashlib.sha256(
        "".join(f"{path}:{file_hashes[path]}\n" for path in sorted(file_hashes)).encode("utf-8")
    ).hexdigest()
    report: dict[str, object] = {
        "schema": "paperagent.academic-holdout.production-scan.v3",
        "production_root": str(root),
        "scanned_file_count": len(files),
        "production_digest": production_digest,
        "private_manifest_sha256": manifest_sha256,
        "private_ngram_count": len(forbidden_ngrams),
        "pilot_recommendation_source_verified": pilot_recommendation_source_verified,
        "passed": not findings,
        "findings": findings,
        "file_sha256": file_hashes,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a frozen PaperAgent tree before holdout execution.")
    parser.add_argument("production_root", type=Path)
    parser.add_argument("--private-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = scan_production(args.production_root, private_manifest=args.private_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
