from __future__ import annotations

import argparse
import json
from pathlib import Path

from paperagent.academic_tailoring_evaluation import evaluate_corpus, load_case_specs
from paperagent.academic_tailoring_fixtures import load_tailoring_task_bundle


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and grade the synthetic academic-tailoring Agent corpus."
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path("evals/academic_tailoring/npc"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evals/academic_tailoring/cases.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/academic-tailoring-eval"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base = load_tailoring_task_bundle(args.fixture_root)
    specs = load_case_specs(args.cases)
    report, tasks, proposals = evaluate_corpus(base, specs)

    output_dir: Path = args.output_dir
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    _write_jsonl(
        output_dir / "case-inputs.jsonl",
        [
            {
                "case_id": spec.case_id,
                "category": spec.category,
                "description": spec.description,
                "expected_decision": spec.expected_decision.value,
                "task": task.model_dump(mode="json"),
            }
            for spec, task in zip(specs, tasks, strict=True)
        ],
    )
    _write_jsonl(
        output_dir / "case-outputs.jsonl",
        [
            {
                "case_id": spec.case_id,
                "proposal": proposal.model_dump(mode="json"),
            }
            for spec, proposal in zip(specs, proposals, strict=True)
        ],
    )
    _write_jsonl(
        output_dir / "grades.jsonl",
        [grade.model_dump(mode="json") for grade in report.grades],
    )
    _write_json(
        output_dir / "main-case-output.json",
        proposals[0].model_dump(mode="json"),
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
