from __future__ import annotations

import json
from pathlib import Path

from paperagent.eval_cli import main


def test_eval_cli_writes_report(tmp_path: Path) -> None:
    cases = tmp_path / "cases.jsonl"
    observations = tmp_path / "observations.jsonl"
    output = tmp_path / "report.json"
    cases.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "version": "v0.6",
                "category": "in_domain",
                "question": "question",
                "expected_terminal": "succeeded",
                "required_properties": ["grounded"],
                "forbidden_properties": [],
                "max_calls": 2,
                "max_cost_usd": 0.1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    observations.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "terminal": "succeeded",
                "observed_properties": ["grounded"],
                "calls": 1,
                "estimated_cost_usd": 0.01,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--cases",
                str(cases),
                "--observations",
                str(observations),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] == 1
