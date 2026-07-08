# Analysis-only script, not runtime code. domain_map is for batch analysis, not pipeline.
"""Re1.5 auto analysis script.

Reads all case state.json files from a directory, analyzes patterns,
and outputs analysis.json with repair_needed flags.

Usage:
    python apps/api/scripts/re15_analyze.py --dir tmp_re15_eval/smoke_20
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_states(eval_dir: Path) -> list[dict]:
    """Load all state.json files from subdirectories."""
    states = []
    for d in sorted(eval_dir.iterdir()):
        if not d.is_dir():
            continue
        state_path = d / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["_case_dir"] = str(d)
            states.append(state)
        except Exception as e:
            print(f"WARNING: failed to load {state_path}: {e}")
    return states


def analyze(states: list[dict]) -> dict:
    """Analyze states and produce report with repair_needed flags."""
    n_cases = len(states)
    n_completed = sum(1 for s in states if s.get("final_recommendation"))

    # Domain stats (infer from case_id mapping)
    domain_map = {
        "ENG-THESIS-015": "医学/人体",
        "ENG-THESIS-016": "三维视觉/SLAM",
        "ENG-THESIS-018": "三维视觉/SLAM",
        "ENG-THESIS-024": "三维视觉/SLAM",
        "ENG-THESIS-027": "遥感/无人机",
        "ENG-THESIS-028": "电力/轨交",
        "ENG-THESIS-032": "工业缺陷",
        "ENG-THESIS-033": "医学",
        "ENG-THESIS-043": "遥感/无人机",
        "ENG-THESIS-046": "机器人",
        "ENG-THESIS-050": "自动驾驶",
        "ENG-THESIS-063": "机器人",
        "ENG-THESIS-066": "自动驾驶",
        "ENG-THESIS-074": "土木",
        "ENG-THESIS-075": "土木",
        "ENG-THESIS-080": "三维视觉",
        "ENG-THESIS-091": "电力/轨交",
        "ENG-THESIS-092": "能源装备",
        "ENG-THESIS-093": "电力/轨交",
        "ENG-THESIS-096": "能源装备",
    }

    domain_stats = defaultdict(lambda: {"n": 0, "n_completed": 0, "accept_counts": [], "n_zero_accept": 0})
    feasibility_verdicts = []
    feasibility_scores = []
    review_verdicts = []
    zero_accept_cases = []

    for s in states:
        case_id = s.get("case_id", "")
        domain = domain_map.get(case_id, "unknown")
        n_papers = len(s.get("verified_papers") or [])
        has_final = bool(s.get("final_recommendation"))

        ds = domain_stats[domain]
        ds["n"] += 1
        if has_final:
            ds["n_completed"] += 1
        ds["accept_counts"].append(n_papers)
        if n_papers == 0:
            ds["n_zero_accept"] += 1
            zero_accept_cases.append(case_id)

        feas = s.get("feasibility_report") or {}
        if feas.get("verdict"):
            feasibility_verdicts.append(feas["verdict"])
        if feas.get("score") is not None:
            try:
                feasibility_scores.append(float(feas["score"]))
            except (ValueError, TypeError):
                pass

        review = s.get("review_report") or {}
        if review.get("overall_verdict"):
            review_verdicts.append(review["overall_verdict"])

    # Compute domain stats
    domain_out = {}
    for domain, ds in domain_stats.items():
        domain_out[domain] = {
            "n": ds["n"],
            "n_completed": ds["n_completed"],
            "avg_accept": round(sum(ds["accept_counts"]) / len(ds["accept_counts"]), 1) if ds["accept_counts"] else 0,
            "n_zero_accept": ds["n_zero_accept"],
        }

    # Feasibility diversity
    unique_feas_verdicts = list(set(feasibility_verdicts))
    feas_all_same = len(unique_feas_verdicts) <= 1
    feas_all_risky = all(v == "risky" for v in feasibility_verdicts) if feasibility_verdicts else False

    score_min = min(feasibility_scores) if feasibility_scores else None
    score_max = max(feasibility_scores) if feasibility_scores else None
    score_spread = round(score_max - score_min, 1) if feasibility_scores else 0

    # Review diversity
    unique_review_verdicts = list(set(review_verdicts))
    review_all_same = len(unique_review_verdicts) <= 1
    review_all_block = all(v == "BLOCK" for v in review_verdicts) if review_verdicts else False

    # Repair needed flags
    repair_needed = {
        "feasibility_prompt": feas_all_same or (score_spread < 20),
        "review_prompt": review_all_same,
        "search_planner_crossref": len(zero_accept_cases) > 0,
    }

    return {
        "n_cases": n_cases,
        "n_completed": n_completed,
        "domain_stats": domain_out,
        "feasibility_stats": {
            "unique_verdicts": unique_feas_verdicts,
            "all_same": feas_all_same,
            "all_risky": feas_all_risky,
            "score_min": score_min,
            "score_max": score_max,
            "score_spread": score_spread,
        },
        "review_stats": {
            "unique_verdicts": unique_review_verdicts,
            "all_same": review_all_same,
            "all_block": review_all_block,
        },
        "zero_accept_cases": zero_accept_cases,
        "repair_needed": repair_needed,
    }


def main():
    parser = argparse.ArgumentParser(description="Re1.5 auto analysis")
    parser.add_argument("--dir", default="tmp_re15_eval", help="Directory with case subdirs")
    args = parser.parse_args()

    eval_dir = Path(args.dir)
    if not eval_dir.exists():
        print(f"ERROR: directory {eval_dir} does not exist")
        return

    states = load_states(eval_dir)
    print(f"Loaded {len(states)} case states from {eval_dir}")

    if not states:
        print("No states found — nothing to analyze")
        return

    result = analyze(states)

    # Save analysis
    out_path = Path("tmp_re15_eval") / "analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n=== Analysis ===")
    print(f"Cases: {result['n_cases']}, Completed: {result['n_completed']}")
    print("\nDomain stats:")
    for domain, ds in result["domain_stats"].items():
        print(f"  {domain}: {ds['n']} cases, avg_accept={ds['avg_accept']}, zero_accept={ds['n_zero_accept']}")
    print("\nFeasibility:")
    print(f"  Verdicts: {result['feasibility_stats']['unique_verdicts']}")
    print(f"  All same: {result['feasibility_stats']['all_same']}")
    print(f"  Score spread: {result['feasibility_stats']['score_spread']}")
    print("\nReview:")
    print(f"  Verdicts: {result['review_stats']['unique_verdicts']}")
    print(f"  All same: {result['review_stats']['all_same']}")
    print(f"\nZero-accept cases: {result['zero_accept_cases']}")
    print(f"\nRepair needed: {result['repair_needed']}")
    print(f"\nAnalysis saved to: {out_path}")


if __name__ == "__main__":
    main()
