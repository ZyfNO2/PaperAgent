"""Generate a public-schema dataset from the authoring dataset.

Strips all gold-standard fields so the result can safely be passed to
run_academic_tailoring_retrieval_v1.py without leakage risk.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path

PUBLIC_SCHEMA = "paperagent.academic-tailoring-retrieval.public.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    auth = json.loads(args.input.read_text(encoding="utf-8"))
    if auth.get("schema") != "paperagent.academic-tailoring-retrieval.authoring.v1":
        raise ValueError(f"unexpected input schema: {auth.get('schema')!r}")

    public_cases = []
    for case in auth.get("cases", []):
        pi = case.get("public_input", {})
        supplied = pi.get("supplied_materials", [])
        public_cases.append(
            {
                "case_id": case["case_id"],
                "benchmark_input": {
                    "user_input": pi.get("user_input", ""),
                    "supplied_material_titles": [m["title"] for m in supplied],
                    "user_declared_roles": [m.get("declared_role", "") for m in supplied],
                    "declared_constraints": [],
                },
            }
        )

    output = {
        "schema": PUBLIC_SCHEMA,
        "dataset_id": auth.get("dataset_id", "academic_tailoring_retrieval_v1"),
        "status": "public_execution_set",
        "generated_from": {
            "source_sha256": hashlib.sha256(
                args.input.read_bytes()
            ).hexdigest(),
            "authoring_commit": auth.get("authoring_commit"),
            "case_count": len(public_cases),
        },
        "cases": public_cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(public_cases)} public cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
