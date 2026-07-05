"""Re1.5 self-test script.

Runs validators on one or all case states.

Usage:
    python apps/api/scripts/re15_self_test.py --case ENG-THESIS-074
    python apps/api/scripts/re15_self_test.py --dir tmp_re15_eval
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tests.self_test.e2e_completeness_validator import validate as validate_e2e
from tests.self_test.paper_authenticity_validator import validate as validate_auth
from tests.self_test.topic_relevance_validator import validate as validate_rel
from tests.self_test.feasibility_diversity_validator import validate_batch as validate_feas_div


def load_state(case_dir: Path) -> dict:
    state_path = case_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"state.json not found in {case_dir}")
    return json.loads(state_path.read_text(encoding="utf-8"))


def run_self_test(state: dict) -> dict:
    """Run all validators on a single case state."""
    return {
        "e2e_completeness": validate_e2e(state),
        "paper_authenticity": validate_auth(state),
        "topic_relevance": validate_rel(state),
    }


def run_batch_self_test(eval_dir: str) -> dict:
    """Run validators on all cases in a directory."""
    eval_path = Path(eval_dir)
    states = []
    case_ids = []

    for d in sorted(eval_path.iterdir()):
        if not d.is_dir():
            continue
        state_path = d / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            states.append(state)
            case_ids.append(state.get("case_id", d.name))
        except Exception as e:
            print(f"WARNING: failed to load {state_path}: {e}")

    per_case = []
    for cid, state in zip(case_ids, states):
        result = run_self_test(state)
        result["case_id"] = cid
        per_case.append(result)

    # Batch-level: feasibility diversity
    feas_div = validate_feas_div(states) if len(states) > 1 else {"pass": False, "details": "need ≥2 cases"}

    overall = all(c.get("e2e_completeness", {}).get("pass", False) for c in per_case)

    return {
        "n_cases": len(states),
        "feasibility_diversity": feas_div,
        "per_case": per_case,
        "overall": overall,
    }


def main():
    parser = argparse.ArgumentParser(description="Re1.5 self-test")
    parser.add_argument("--case", help="Single case ID (e.g., ENG-THESIS-074)")
    parser.add_argument("--dir", default="tmp_re15_eval", help="Directory with case subdirs")
    args = parser.parse_args()

    if args.case:
        # Single case
        case_dir = Path(args.dir) / args.case
        if not case_dir.exists():
            print(f"ERROR: case directory {case_dir} not found")
            return
        state = load_state(case_dir)
        result = run_self_test(state)
        result["case_id"] = args.case
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        # Save report
        report_path = Path("tmp_re15_eval") / f"self_test_{args.case}.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\nReport saved to: {report_path}")
    else:
        # Batch
        result = run_batch_self_test(args.dir)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        # Save report
        report_path = Path("tmp_re15_eval") / "self_test_report.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\nReport saved to: {report_path}")

        # Summary
        n_pass_e2e = sum(1 for c in result["per_case"] if c.get("e2e_completeness", {}).get("pass"))
        n_pass_auth = sum(1 for c in result["per_case"] if c.get("paper_authenticity", {}).get("pass"))
        n_pass_rel = sum(1 for c in result["per_case"] if c.get("topic_relevance", {}).get("pass"))
        print(f"\n=== Summary ===")
        print(f"e2e_completeness: {n_pass_e2e}/{result['n_cases']} pass")
        print(f"paper_authenticity: {n_pass_auth}/{result['n_cases']} pass")
        print(f"topic_relevance: {n_pass_rel}/{result['n_cases']} pass")
        print(f"feasibility_diversity: {'pass' if result['feasibility_diversity'].get('pass') else 'fail'}")


if __name__ == "__main__":
    main()
