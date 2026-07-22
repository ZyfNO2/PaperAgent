from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from paperagent.eval_runtime_reporting import canonical_sha256

ROOT = Path("artifacts/eval-runs")
OLD = ROOT / "run-20260723-003-final"
NEW = ROOT / "run-20260723-003-partial"
AUTHORING = Path("evals/academic_tailoring_retrieval_v1/dataset-authoring.json")
PUBLIC = ROOT / "public-dataset.json"
AUTHORING_COMMIT = "36fb2af792ad51c442262a89124869a2b57954c6"
SNAPSHOT_COMMIT = "b6c22517cd46f29a6403c60f706e3bffb909006b"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OLD.exists() and NEW.exists():
        raise RuntimeError("both legacy final and partial snapshot directories exist")
    if OLD.exists():
        OLD.rename(NEW)
    if not NEW.is_dir():
        raise RuntimeError("legacy snapshot directory is missing")

    authoring = _load(AUTHORING)
    public = _load(PUBLIC)
    generated_from = public.setdefault("generated_from", {})
    if not isinstance(generated_from, dict):
        raise ValueError("public generated_from must be an object")
    generated_from.clear()
    generated_from.update(
        {
            "authoring_sha256": canonical_sha256(authoring),
            "authoring_commit": AUTHORING_COMMIT,
            "case_count": len(public.get("cases", [])),
        }
    )
    public.pop("public_sha256", None)
    public["public_sha256"] = canonical_sha256(public)
    _write(PUBLIC, public)
    shutil.copy2(PUBLIC, NEW / "public-dataset.json")

    old_manifest = _load(NEW / "manifest.json")
    summary = _load(NEW / "execution-summary.json")
    summary["source_sha"] = old_manifest.get("source_commit")
    summary["public_dataset_sha256"] = public["public_sha256"]
    summary["runtime_errors"] = len(summary.get("errors", []))
    summary["run_status"] = "partial"
    summary["scientific_acceptance"] = False
    _write(NEW / "execution-summary.json", summary)

    readme = """# Legacy partial diagnostic snapshot

This directory was originally named `run-20260723-003-final`, but the runtime
summary records only 6 completed cases out of 10 and 4 incomplete executions.
It is retained as a diagnostic artifact only.

The original run did not record trustworthy start/end timing or duration. Those
values are not reconstructed. Consequently this directory intentionally does
not use the strict `paperagent.eval-run.manifest.v2` schema and must not be
presented as a reproducible or scientifically accepted snapshot.
"""
    (NEW / "README.md").write_text(readme, encoding="utf-8")

    files = {
        path.name: _sha(path)
        for path in sorted(NEW.iterdir())
        if path.is_file() and path.name not in {"manifest.json", "checksums.sha256"}
    }
    (NEW / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(files.items())),
        encoding="utf-8",
    )
    manifest = {
        "schema": "paperagent.eval-run.legacy-diagnostic.v1",
        "run_id": "run-20260723-003",
        "artifact_directory": NEW.name,
        "run_status": "partial",
        "scientific_acceptance": False,
        "validation_status": "invalid_legacy_timing_unavailable",
        "validation_notes": [
            "Only 6 of 10 cases completed.",
            "Four runtime errors were recorded.",
            "Original start/end timing and duration are unavailable.",
            "This artifact is retained for diagnosis, not acceptance.",
        ],
        "dataset_id": public.get("dataset_id"),
        "public_dataset_sha256": public["public_sha256"],
        "authoring_dataset_sha256": generated_from["authoring_sha256"],
        "authoring_commit": AUTHORING_COMMIT,
        "run_source_commit": old_manifest.get("source_commit"),
        "snapshot_commit": SNAPSHOT_COMMIT,
        "source_branch": old_manifest.get("source_branch"),
        "scorer_version": old_manifest.get("scorer_version"),
        "case_count": summary.get("selected_case_count"),
        "attempted": len(summary.get("attempted_case_ids", [])),
        "completed": summary.get("completed"),
        "runtime_errors": summary.get("runtime_errors"),
        "files": files,
    }
    _write(NEW / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
