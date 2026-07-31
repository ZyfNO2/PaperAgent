"""Human-review acceptance package for the two frozen H3 tailoring scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from paperagent.academic.contracts import FrozenAcademicModel


class TailoringScenario(FrozenAcademicModel):
    scenario_id: str
    hypothesis: str
    baseline_paper_id: str
    module_paper_ids: tuple[str, ...] = Field(min_length=1)
    corpus_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_decision: Literal["GO", "REVISE", "NO-GO"] | None = None
    expected_claims: tuple[str, ...] = ()
    reviewer_notes: str | None = None

    @model_validator(mode="after")
    def require_distinct_papers(self) -> TailoringScenario:
        if self.baseline_paper_id in self.module_paper_ids:
            raise ValueError("baseline paper cannot also be a module paper")
        return self


class TailoringAcceptancePackage(FrozenAcademicModel):
    schema_version: Literal["academic-h3-acceptance.v1"]
    status: Literal["blocked_by_human_review", "ready_for_automated_run"]
    scenarios: tuple[TailoringScenario, ...]
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    missing_human_fields: tuple[str, ...]
    instructions: tuple[str, ...]


def load_tailoring_acceptance_package(path: Path) -> TailoringAcceptancePackage:
    raw = path.read_bytes()
    payload = json.loads(raw)
    scenarios = tuple(TailoringScenario.model_validate(item) for item in payload["scenarios"])
    if len(scenarios) != 2:
        raise ValueError("exactly two frozen tailoring scenarios are required")
    if len({scenario.scenario_id for scenario in scenarios}) != 2:
        raise ValueError("scenario IDs must be unique")
    missing = tuple(
        f"{scenario.scenario_id}.{field}"
        for scenario in scenarios
        for field in ("expected_decision", "expected_claims", "reviewer_notes")
        if not getattr(scenario, field)
    )
    status: Literal["blocked_by_human_review", "ready_for_automated_run"] = (
        "blocked_by_human_review" if missing else "ready_for_automated_run"
    )
    return TailoringAcceptancePackage(
        schema_version="academic-h3-acceptance.v1",
        status=status,
        scenarios=scenarios,
        source_digest=hashlib.sha256(raw).hexdigest(),
        missing_human_fields=missing,
        instructions=(
            "A reviewer must inspect the cited papers and fill expected_decision.",
            "Expected claims must contain only human-approved evidence-bound claims.",
            "Do not infer missing labels with a FakeModel or deterministic draft.",
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario_file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    package = load_tailoring_acceptance_package(args.scenario_file)
    encoded = package.model_dump_json(indent=2).encode("utf-8") + b"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    else:
        print(encoded.decode("utf-8"), end="")
    return 2 if package.status == "blocked_by_human_review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
