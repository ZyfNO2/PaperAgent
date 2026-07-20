from __future__ import annotations

import argparse
from pathlib import Path

from paperagent.claw_benchmark_adapter import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.claw_trace_reconciliation import reconcile_ledger_relevance
from paperagent.state import state_from_json


def _read_nonblank(path: Path) -> tuple[str, ...]:
    lines = tuple(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if not lines:
        raise ValueError(f"{path} must contain at least one non-blank JSON line")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize serialized PaperAgent states into Claw benchmark run traces."
    )
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    state_lines = _read_nonblank(args.states)
    context_lines = _read_nonblank(args.contexts)
    if len(state_lines) != len(context_lines):
        raise ValueError(
            "state and normalization-context JSONL files must contain the same number of rows"
        )

    traces = []
    seen_case_ids: set[str] = set()
    for row_number, (state_line, context_line) in enumerate(
        zip(state_lines, context_lines, strict=True), start=1
    ):
        try:
            state = state_from_json(state_line)
            context = BenchmarkNormalizationContext.model_validate_json(context_line)
            if context.case_id in seen_case_ids:
                raise ValueError(f"duplicate case_id {context.case_id!r}")
            seen_case_ids.add(context.case_id)
            trace = normalize_paperagent_state(state, context)
            traces.append(reconcile_ledger_relevance(state, trace))
        except ValueError as exc:
            raise ValueError(f"row {row_number}: {exc}") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(item.model_dump_json(by_alias=True) for item in traces) + "\n",
        encoding="utf-8",
    )
    print(f"normalized {len(traces)} PaperAgent states to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
