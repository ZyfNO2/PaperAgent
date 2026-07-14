"""Re8.2 WP4: run a single seeded demo case and persist full artifacts.

Produces the following files under ``artifacts/re8_2/final/<case_key>/``:
  - summary.json            public metrics + gate results + pass tiers
  - state.json              full final LangGraph state
  - trace.json              trace_events
  - gate_cycles.json        reflection_gate_results per gate
  - seed_candidates.json    seed_cards after resolver
  - final_package.json      final_research_package

Usage:
  python apps/api/scripts/re82_wp4_case_runner.py --case vit_dr
  python apps/api/scripts/re82_wp4_case_runner.py --case xlm_r
  python apps/api/scripts/re82_wp4_case_runner.py --case yolo_steel
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.api.scripts.re80_seeded_demo import CASES, run_seeded_demo


def _serialize(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def run_case(case_key: str) -> dict:
    """Run one case and write artifacts. Returns the public summary."""
    result = run_seeded_demo(case_key)

    out_dir = Path(ROOT) / "artifacts" / "re8_2" / "final" / case_key
    out_dir.mkdir(parents=True, exist_ok=True)

    final_state = result.pop("_final_state", None)

    # Public summary (no giant state)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(_serialize(result), encoding="utf-8")

    if final_state is not None:
        # Full final state
        (out_dir / "state.json").write_text(_serialize(final_state), encoding="utf-8")

        # Trace events
        trace_events = final_state.get("trace_events") or []
        (out_dir / "trace.json").write_text(_serialize(trace_events), encoding="utf-8")

        # Gate cycles (full round-by-round)
        gate_results = final_state.get("reflection_gate_results") or {}
        (out_dir / "gate_cycles.json").write_text(_serialize(gate_results), encoding="utf-8")

        # Seed candidates / audited cards
        seed_cards = final_state.get("seed_cards") or []
        (out_dir / "seed_candidates.json").write_text(_serialize(seed_cards), encoding="utf-8")

        # Final research package
        final_package = final_state.get("final_research_package") or {}
        (out_dir / "final_package.json").write_text(_serialize(final_package), encoding="utf-8")

    print(f"[wp4] {case_key}: artifacts written to {out_dir}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=list(CASES.keys()))
    args = parser.parse_args()

    result = run_case(args.case)
    summary = {
        "case_key": args.case,
        "status": result.get("status"),
        "runtime_pass": result.get("runtime_pass"),
        "contract_pass": result.get("contract_pass"),
        "quality_pass": result.get("quality_pass"),
        "fused_verdict": result.get("fused_verdict"),
        "elapsed_s": result.get("elapsed_s"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("quality_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
