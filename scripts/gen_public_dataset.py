"""Generate a provenance-bound public dataset from the authoring dataset.

This is a compatibility wrapper around the canonical projection implementation in
``project_academic_tailoring_retrieval_v1.py``. Gold fields never cross the output
boundary, declared constraints are preserved, and the canonical public digest is
embedded in the generated file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_academic_tailoring_retrieval_v1 import (
    _load_json,
    _require_authoring_commit,
    project_public_dataset,
    verify_gold_mutation_invariance,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authoring-commit", default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    authoring = _load_json(args.input)
    authoring_commit = _require_authoring_commit(authoring, args.authoring_commit)
    verify_gold_mutation_invariance(
        authoring,
        authoring_commit=authoring_commit,
    )
    public = project_public_dataset(
        authoring,
        authoring_commit=authoring_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "case_count": len(public["cases"]),
                "authoring_commit": authoring_commit,
                "authoring_sha256": public["generated_from"]["authoring_sha256"],
                "public_sha256": public["public_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
