"""Re3.9: Analyze the source of every dataset/repo/baseline across all eval data.

For each case, outputs:
- Which datasets came from LLM extraction vs heuristic vs cross_node scan
- Which repos came from search_agent vs citation_expander
- Which baselines came from LLM classification vs heuristic
- Whether any node used heuristic fallback (provider="heuristic")
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

EVAL_DIRS = [
    "tmp_re13_eval",
    "tmp_re34_eval",
    "tmp_re35_eval",
    "tmp_re36_eval",
    "tmp_re38_eval",
]


def analyze_case(case_path: str) -> dict | None:
    state_path = os.path.join(case_path, "state.json")
    trace_path = os.path.join(case_path, "trace.json")
    if not os.path.exists(state_path):
        return None

    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    trace = []
    if os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)

    # Dataset sources
    datasets = state.get("dataset_candidates") or []
    ds_sources = Counter(d.get("source", "unknown") for d in datasets)

    # Repo sources
    repos = state.get("repo_candidates") or []
    repo_sources = Counter(r.get("source", "unknown") for r in repos)

    # Heuristic nodes
    heuristic_nodes = []
    for ev in trace:
        if ev.get("provider") == "heuristic":
            heuristic_nodes.append(ev.get("node", "?"))

    # Fallback flag in dataset_repo trace
    ds_used_fallback = False
    for ev in trace:
        if ev.get("node") in ("dataset_repo", "dataset_repo_extractor"):
            out = ev.get("output_summary", {})
            if out.get("used_fallback"):
                ds_used_fallback = True
            break

    # Innovation mentions datasets?
    inn = state.get("innovation_points") or []
    inn_text = " ".join(
        [str(i.get("description", "")) + str(i.get("stitching_plan", "")) for i in inn]
    )

    # Cross-node datasets found by innovation_extractor
    cross_node_ds = [
        d for d in datasets
        if d.get("source") == "cross_node:innovation_extractor"
    ]

    return {
        "n_datasets": len(datasets),
        "ds_sources": dict(ds_sources),
        "n_repos": len(repos),
        "repo_sources": dict(repo_sources),
        "heuristic_nodes": heuristic_nodes,
        "ds_used_fallback": ds_used_fallback,
        "inn_mentions_dataset": bool(inn_text)
        and any(kw in inn_text.lower() for kw in ["dataset", "benchmark", "数据集"]),
        "cross_node_datasets": len(cross_node_ds),
    }


def main() -> None:
    results: dict[str, dict] = {}
    for eval_dir in EVAL_DIRS:
        if not os.path.exists(eval_dir):
            continue
        for case_dir in sorted(os.listdir(eval_dir)):
            case_path = os.path.join(eval_dir, case_dir)
            if not os.path.isdir(case_path):
                continue
            analysis = analyze_case(case_path)
            if analysis:
                results[f"{eval_dir}/{case_dir}"] = analysis

    print("=" * 80)
    print("Re3.9 Provenance Analysis")
    print("=" * 80)

    all_heuristic: list[tuple[str, list[str]]] = []
    all_ds_sources: Counter = Counter()
    all_repo_sources: Counter = Counter()
    all_fallback = 0
    all_cross_node = 0

    for case_id, a in results.items():
        if a["heuristic_nodes"]:
            all_heuristic.append((case_id, a["heuristic_nodes"]))
        for src, cnt in a["ds_sources"].items():
            all_ds_sources[src] += cnt
        for src, cnt in a["repo_sources"].items():
            all_repo_sources[src] += cnt
        if a["ds_used_fallback"]:
            all_fallback += 1
        if a["cross_node_datasets"] > 0:
            all_cross_node += a["cross_node_datasets"]

    print(f"\nTotal cases: {len(results)}")
    print(f"Cases with heuristic fallback: {len(all_heuristic)}")
    if all_heuristic:
        for case, nodes in all_heuristic:
            print(f"  {case}: {nodes}")
    else:
        print("  (none — all LLM-driven)")

    print("\nDataset sources across all cases:")
    for src, cnt in all_ds_sources.most_common():
        print(f"  {src}: {cnt}")

    print("\nRepo sources across all cases:")
    for src, cnt in all_repo_sources.most_common():
        print(f"  {src}: {cnt}")

    print(f"\nCases where dataset_repo used fallback: {all_fallback}")
    print(f"Cross-node datasets found: {all_cross_node}")

    # Per-case detail
    print(f"\n{'='*80}")
    print("Per-case details:")
    print(f"{'='*80}")
    for case_id, a in sorted(results.items()):
        print(
            f"{case_id:45s}: ds={a['n_datasets']:2d} repos={a['n_repos']:2d} "
            f"heur={len(a['heuristic_nodes'])} fallback={a['ds_used_fallback']} "
            f"cross_node={a['cross_node_datasets']}"
        )

    # Save JSON report
    out_dir = Path("tmp_re39_eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "provenance_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to: {out_dir / 'provenance_report.json'}")


if __name__ == "__main__":
    main()
