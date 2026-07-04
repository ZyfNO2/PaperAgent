"""Fixed audit - correctly read traces and batch files."""
import json
from pathlib import Path

TRACE_DIR = Path("tmp_re04_eval/balanced40_re10_reflection_fix3/traces")
BATCH_DIR = Path("tmp_re04_eval/balanced40_re10_reflection_fix3/batch1")

GENERIC_REPOS = {"orb-slam3", "orb_slam3", "open_vins", "openvins", "awesome-visual-slam",
                 "orb_slam_3", "dynoslam", "dvoslam", "slam"}
SLAM_KW = {"slam", "visual odometry", "visual-inertial", "semantic", "dynamic slam"}
STEEL_KW = {"steel", "表面缺陷"}

def is_slam(t: str) -> bool:
    t = t.lower()
    return any(k in t for k in SLAM_KW) and any(k in t for k in {"slam", "visual odometry"})

def has_fallback(qs):
    return any("[Fallback]" in q for q in qs)

def has_steel(qs):
    return any("steel" in q.lower() for q in qs)

def has_orb(qs):
    return any("orb-slam" in q.lower() or "orb_slam" in q.lower() for q in qs)

traces = sorted(TRACE_DIR.glob("ENG-THESIS-*.json"))
print(f"{'Case':<20} {'Rounds':<8} {'Queries':<8} {'Fallback':<10} {'Contam':<10} {'ORB_SLAM':<10} {'Papers':<8}")
print("="*85)
issues = []
for tp in traces:
    cid = tp.stem
    trace = json.loads(tp.read_text(encoding="utf-8"))
    topic = trace.get("topic", "")
    rounds_data = trace.get("rounds", [])
    rounds_n = len(rounds_data)
    
    # Collect queries
    all_q = []
    for r in rounds_data:
        for a in r.get("actions", []):
            q = a.get("query", "")
            if q:
                all_q.append(q)
    
    # Check batch for final_candidate_pool
    bf = BATCH_DIR / f"{cid}.json"
    if bf.exists():
        b = json.loads(bf.read_text(encoding="utf-8"))
        pool = b.get("final_candidate_pool") or []
        paper_n = sum(1 for c in pool if c.get("_bucket") in ("paper", "core_paper"))
    else:
        pool = []
        paper_n = -1
    
    fb = has_fallback(all_q)
    st = has_steel(all_q) and "steel" not in topic.lower() and "表面缺陷" not in topic
    orb = has_orb(all_q) and not is_slam(topic)
    
    contam = ""
    if st:
        contam = "STEEL"
    if orb:
        contam += "+ORB" if contam else "ORB"
    if not contam:
        contam = "CLEAN"
    
    fb_str = "YES" if fb else "-"
    
    if contam != "CLEAN" or fb:
        issues.append(f"  {cid}: contam={contam}, fallback={fb_str}")
    
    print(f"{cid:<20} {rounds_n:<8} {len(all_q):<8} {fb_str:<10} {contam:<10} {('YES' if orb else '-'):<10} {paper_n:<8}")

print(f"\n=== Issues ({len(issues)}) ===")
for i in issues:
    print(i)
