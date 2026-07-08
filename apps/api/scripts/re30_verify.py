"""Re3.0 verification script — inspect state.json and run §4.3 self-checks.

Usage:
    python apps/api/scripts/re30_verify.py --dir tmp_re30_eval/verify2
    python apps/api/scripts/re30_verify.py --dir tmp_re30_eval/batch20 --ground-truth tmp_re30_eval/ground_truth/verified_ground_truth.json
"""
import argparse
import json
from pathlib import Path


def _load_state(case_dir: Path) -> dict:
    sf = case_dir / "state.json"
    if not sf.exists():
        return {}
    return json.loads(sf.read_text(encoding="utf-8"))


def _check_case(case_id: str, state: dict, gt: list | None = None) -> dict:
    """Run §4.3 self-checks on a single case."""
    result = {"case_id": case_id, "checks": {}, "pass": True}

    topic = state.get("topic", "")
    atoms = state.get("topic_atoms") or {}
    method = atoms.get("method") or []
    obj = atoms.get("object") or []

    # Rule 1: Query words match topic
    traces = state.get("trace_events") or []
    search_traces = [t for t in traces if t.get("node") in ("retrieve", "paper_retriever", "search_agent")]
    tool_calls = []
    for t in search_traces:
        tool_calls.extend(t.get("tool_calls") or [])
    search_steps = state.get("search_steps") or []
    step_queries = [s.get("query", "") for s in search_steps if s.get("type") == "tool_call"]

    # Check if queries contain topic keywords
    topic_keywords = set()
    for m in method:
        topic_keywords.add(m.lower())
    for o in obj:
        topic_keywords.add(o.lower())

    has_deep_learning = False
    # Only flag "deep learning" if topic doesn't contain it as a keyword
    # (i.e. "基于深度学习" topics legitimately have "deep learning" in queries)
    topic_has_dl = "deep learning" in topic.lower() or "深度学习" in topic
    for q in step_queries:
        if "deep learning" in q.lower() and not topic_has_dl:
            has_deep_learning = True

    query_aligned = True
    if topic_keywords:
        query_aligned = any(
            any(kw in q.lower() for kw in topic_keywords)
            for q in step_queries
        ) or not step_queries  # no steps = old retrieve path

    result["checks"]["rule1_query_aligned"] = query_aligned
    result["checks"]["has_deep_learning_fallback"] = has_deep_learning
    if not query_aligned or has_deep_learning:
        result["pass"] = False

    # Rule 2: Papers relevant to topic
    verified = state.get("verified_papers") or []
    weak = state.get("weak_papers") or []
    all_papers = verified + weak
    paper_titles = [p.get("title", "") for p in all_papers]

    # Check for garbage indicators
    garbage_indicators = ["Deep Learning 500 Questions", "keras-team/keras",
                          "annotated_deep_learning_paper_implementations"]
    has_garbage = any(g in " ".join(paper_titles) for g in garbage_indicators)

    result["checks"]["rule2_no_garbage"] = not has_garbage
    result["checks"]["n_verified"] = len(verified)
    result["checks"]["n_weak"] = len(weak)
    if has_garbage:
        result["pass"] = False

    # Rule 3: GitHub repos not in paper list
    github_in_papers = any(p.get("source") == "github" for p in all_papers)
    result["checks"]["rule3_no_github_in_papers"] = not github_in_papers
    if github_in_papers:
        result["pass"] = False

    # Rule 4: repo/dataset extraction
    repos = state.get("repo_candidates") or []
    datasets = state.get("dataset_candidates") or []
    repo_urls_ok = all("github.com" in (r.get("url") or "") and "api.github.com" not in (r.get("url") or "")
                       for r in repos) if repos else True
    result["checks"]["n_repos"] = len(repos)
    result["checks"]["n_datasets"] = len(datasets)
    result["checks"]["rule4_repo_urls_ok"] = repo_urls_ok
    if not repo_urls_ok:
        result["pass"] = False

    # Rule 5: No duplicate papers
    titles_lower = [t.lower().strip() for t in paper_titles if t]
    duplicates = len(titles_lower) - len(set(titles_lower))
    result["checks"]["rule5_duplicates"] = duplicates
    if duplicates > 0:
        result["pass"] = False

    # Rule 6: No non-paper entries
    non_paper = any(t.startswith("Table ") or t.startswith("Figure ") for t in paper_titles)
    result["checks"]["rule6_no_nonpaper"] = not non_paper
    if non_paper:
        result["pass"] = False

    # Rule 7: Feasibility
    feas = state.get("feasibility_report") or {}
    feas_verdict = feas.get("verdict", "")
    result["checks"]["feasibility"] = feas_verdict
    result["checks"]["feasibility_score"] = feas.get("score", 0)

    # React search steps check
    n_tool_calls = sum(1 for s in search_steps if s.get("type") == "tool_call")
    result["checks"]["n_search_steps"] = n_tool_calls
    result["checks"]["has_react_search"] = n_tool_calls >= 2

    # Narrative check (Fix 2.1)
    narrative = state.get("research_narrative") or state.get("research_narrative")
    result["checks"]["has_narrative"] = bool(narrative)
    if not narrative and len(verified) > 0:
        result["pass"] = False

    # Revision count check (Fix 2.2)
    rc = state.get("narrative_revision_count", 0)
    result["checks"]["revision_count"] = rc

    # Ground truth comparison
    if gt:
        gt_match = next((g for g in gt if case_id in g.get("cases", [])), None)
        if gt_match:
            gt_keywords = [k.lower() for k in gt_match.get("keywords", [])]
            keyword_coverage = sum(1 for k in gt_keywords if any(k in q.lower() for q in step_queries)) / max(len(gt_keywords), 1)
            result["checks"]["gt_keyword_coverage"] = round(keyword_coverage, 2)
            result["checks"]["gt_feasibility"] = gt_match.get("feasibility", "")
            result["checks"]["gt_feasibility_aligned"] = (gt_match.get("feasibility") == feas_verdict) or \
                (gt_match.get("feasibility") == "feasible" and feas_verdict in ("feasible", "risky")) or \
                (gt_match.get("feasibility") == "risky" and feas_verdict in ("feasible", "risky")) or \
                (gt_match.get("feasibility") == "not_recommended" and feas_verdict == "not_recommended")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory with case subdirectories")
    parser.add_argument("--ground-truth", default="tmp_re30_eval/ground_truth/verified_ground_truth.json")
    args = parser.parse_args()

    base = Path(args.dir)
    gt = None
    if args.ground_truth and Path(args.ground_truth).exists():
        gt = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))

    case_dirs = [d for d in base.iterdir() if d.is_dir() and (d / "state.json").exists()]
    case_dirs.sort()

    print(f"Re3.0 verification: {len(case_dirs)} cases in {base}")
    print()

    all_pass = True
    for cd in case_dirs:
        case_id = cd.name
        state = _load_state(cd)
        if not state:
            print(f"  {case_id}: NO STATE (error)")
            all_pass = False
            continue

        result = _check_case(case_id, state, gt)
        status = "PASS" if result["pass"] else "FAIL"
        if not result["pass"]:
            all_pass = False

        n_papers = result["checks"].get("n_verified", 0)
        n_repos = result["checks"].get("n_repos", 0)
        feas = result["checks"].get("feasibility", "?")
        n_steps = result["checks"].get("n_search_steps", 0)
        has_narrative = result["checks"].get("has_narrative", False)

        print(f"  {case_id}: {status} | papers={n_papers}, repos={n_repos}, "
              f"feas={feas}, steps={n_steps}, narrative={'Y' if has_narrative else 'N'}")

        # Print failed checks
        for check_name, check_val in result["checks"].items():
            if check_name == "rule5_duplicates":
                if check_val > 0:
                    print(f"    FAIL: {check_name} ({check_val} duplicates)")
            elif check_name.startswith("rule") and not check_val:
                print(f"    FAIL: {check_name}")
            elif check_name == "has_deep_learning_fallback" and check_val:
                print("    FAIL: deep learning fallback detected")

    print()
    print(f"Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")


if __name__ == "__main__":
    main()
