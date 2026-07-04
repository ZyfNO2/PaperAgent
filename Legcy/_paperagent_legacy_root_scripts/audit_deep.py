"""Deep audit: check query redundancy, SLAM cases, and ORB_SLAM3 in allowed contexts."""
import json
from pathlib import Path

BASE = Path("tmp_re04_eval/balanced40_re10_reflection_fix3")
TRACE_DIR = BASE / "traces"

SLAM_IDS = {"ENG-THESIS-016", "ENG-THESIS-048", "ENG-THESIS-051", "ENG-THESIS-072"}
STEEL_ID = "ENG-THESIS-022"  # 钢铁表面缺陷

traces = sorted(TRACE_DIR.glob("ENG-THESIS-*.json"))

# 1. Query redundancy check
print("=== Query Word Redundancy ===")
for tp in traces:
    cid = tp.stem
    trace = json.loads(tp.read_text(encoding="utf-8"))
    all_q = []
    for r in trace.get("rounds", []):
        for a in r.get("actions", []):
            q = a.get("query", "")
            if q:
                all_q.append(q)
    # Check for repeated words in queries
    for q in all_q:
        words = q.lower().split()
        for i in range(len(words)-1):
            if words[i] == words[i+1]:
                print(f"  {cid}: REPEATED WORD '{words[i]}' in: {q[:80]}")
                break

# 2. SLAM cases: check ORB-SLAM3 presence
print("\n=== SLAM Cases - ORB-SLAM3 Check ===")
for cid in sorted(SLAM_IDS):
    tp = TRACE_DIR / f"{cid}.json"
    if not tp.exists():
        continue
    trace = json.loads(tp.read_text(encoding="utf-8"))
    # Check all batch dirs for final pool
    orb_found = False
    for bd in sorted(BASE.glob("batch*")):
        bf = bd / f"{cid}.json"
        if bf.exists():
            b = json.loads(bf.read_text(encoding="utf-8"))
            pool = b.get("final_candidate_pool") or []
            for c in pool:
                title = c.get("title", "")
                if "orb-slam3" in title.lower() or "orb_slam3" in title.lower():
                    orb_found = True
                    print(f"  {cid}: ORB-SLAM3 found in pool (ALLOWED): {title[:60]}")
    if not orb_found:
        print(f"  {cid}: ORB-SLAM3 NOT in pool")

# 3. Sample query quality
print("\n=== Sample Queries by Domain ===")
for tp in traces[:10]:  # First 10
    cid = tp.stem
    trace = json.loads(tp.read_text(encoding="utf-8"))
    r1 = trace.get("rounds", [{}])[0]
    if r1:
        queries = [a.get("query", "") for a in r1.get("actions", [])]
        print(f"\n{cid} ({trace.get('topic', '')[:30]}):")
        for q in queries:
            print(f"  - {q}")
