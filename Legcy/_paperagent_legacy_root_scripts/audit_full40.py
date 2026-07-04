"""Audit all 40 Balanced10 traces for contamination, fallback issues, and query quality."""
import json
from pathlib import Path

TRACE_DIR = Path("tmp_re04_eval/balanced40_re10_reflection/traces")
TRACES = sorted(TRACE_DIR.glob("ENG-THESIS-*.json"))

# Known generic repos to flag
GENERIC_REPOS = {"orb-slam3", "orb_slam3", "open_vins", "openvins", "awesome-visual-slam",
                 "orb_slam_3", "orb_slam", "dynoslam", "dvoslam", "slam"}

SLAM_KEYWORDS = {"slam", "visual odometry", "visual-inertial", "multimap slam",
                 "semantic slam", "dynamic slam", "visual localization"}

PAPER_DIR = Path("tmp_re04_eval/balanced40_re10_reflection/batch1")

def is_slam_topic(topic: str) -> bool:
    low = topic.lower()
    return any(kw in low for kw in SLAM_KEYWORDS)

print(f"Scanning {len(TRACES)} traces...\n")

results = []
for tp in TRACES:
    cid = tp.stem
    trace = json.loads(tp.read_text(encoding="utf-8"))
    topic = trace.get("topic", "")
    rounds = trace.get("rounds", [])
    
    # Collect all queries across rounds
    all_queries = []
    for r in rounds:
        for a in r.get("actions", []):
            q = a.get("query", "")
            if q:
                all_queries.append(q)
    
    # Check for [Fallback]
    has_fallback = any("[Fallback]" in q for q in all_queries)
    
    # Check for cross-contamination: steel surface in non-steel topics
    has_steel = any("steel" in q.lower() for q in all_queries)
    is_steel_topic = "steel" in topic.lower() or "缺陷" in topic
    
    # Check for ORB_SLAM3
    has_orb = any("orb-slam" in q.lower() or "orb_slam" in q.lower() for q in all_queries)
    
    # Check round count
    round_count = len([r for r in rounds if r.get("actions")])
    
    issues = []
    if has_fallback:
        issues.append("FALLBACK_LABEL")
    if has_steel and not is_steel_topic:
        issues.append(f"CROSS_CONTAM(steel) topic={topic[:30]}")
    if has_orb and not is_slam_topic(topic):
        issues.append(f"ORB_SLAM_QUERY topic={topic[:30]}")
    if round_count < 3:
        issues.append(f"ONLY_{round_count}_ROUNDS")
    
    # Check batch file for final_candidate_pool
    batch_path = PAPER_DIR / f"{cid}.json"
    if batch_path.exists():
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        pool = batch.get("final_candidate_pool") or []
        paper_n = len(pool)
        # Check generic repos in pool
        repo_titles = [c.get("title", "") for c in pool if c.get("_bucket") == "repo"]
        generic_repo_hits = [t for t in repo_titles if any(gr in t.lower() for gr in GENERIC_REPOS)]
        if generic_repo_hits and not is_slam_topic(topic):
            issues.append(f"GENERIC_REPO_POOL: {generic_repo_hits[:3]}")
        if not is_slam_topic(topic):
            orb_in_pool = any("orb-slam3" in (c.get("title") or "").lower() for c in pool)
            if orb_in_pool:
                issues.append(f"ORB_SLAM3_IN_POOL")
    else:
        pool = []
        paper_n = 0
    
    status = "OK" if not issues else "; ".join(issues)
    results.append((cid, topic[:60], round_count, len(all_queries), paper_n, status))

# Print results
print(f"{'Case':<20} {'Topic':<50} {'Rnd':<5} {'Q':<5} {'Papers':<8} Status")
print("="*110)
for cid, topic, rnd, nq, papers, status in results:
    print(f"{cid:<20} {topic[:50]:<50} {rnd:<5} {nq:<5} {papers:<8} {status}")

# Summary
print(f"\n=== SUMMARY ===")
issues_cases = [r for r in results if r[5] != "OK"]
ok_cases = [r for r in results if r[5] == "OK"]
print(f"Total: {len(results)}, Clean: {len(ok_cases)}, Issues: {len(issues_cases)}")
for r in issues_cases:
    print(f"  {r[0]}: {r[5]}")

# Batch1 check
print(f"\n=== Batch1 files ===")
batch_files = sorted(PAPER_DIR.glob("ENG-THESIS-*.json"))
print(f"{len(batch_files)} batch files found")
for bf in batch_files:
    cid = bf.stem
    try:
        b = json.loads(bf.read_text(encoding="utf-8"))
    except:
        continue
    pool = b.get("final_candidate_pool") or []
    paper_n = sum(1 for c in pool if c.get("_bucket") == "paper")
    repo_n = sum(1 for c in pool if c.get("_bucket") == "repo")
    dataset_n = sum(1 for c in pool if c.get("_bucket") == "dataset")
    if paper_n < 5:
        print(f"  {cid}: papers={paper_n}, repos={repo_n}, datasets={dataset_n} (LOW PAPERS)")
