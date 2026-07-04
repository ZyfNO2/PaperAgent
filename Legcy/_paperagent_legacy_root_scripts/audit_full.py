"""Full audit with all batch directories."""
import json
from pathlib import Path

BASE = Path("tmp_re04_eval/balanced40_re10_reflection_fix3")
TRACE_DIR = BASE / "traces"

# Find all batch dirs
batch_dirs = list(BASE.glob("batch*"))
print(f"Batch dirs: {[d.name for d in sorted(batch_dirs)]}")

# Find all batch files
paper_counts = {}
for bd in sorted(batch_dirs):
    for bf in sorted(bd.glob("ENG-THESIS-*.json")):
        cid = bf.stem
        try:
            b = json.loads(bf.read_text(encoding="utf-8"))
        except Exception as e:
            paper_counts[cid] = -2
            continue
        pool = b.get("final_candidate_pool") or []
        paper_n = sum(1 for c in pool if c.get("_bucket") in ("paper", "core_paper")) if pool else len(pool)
        paper_counts[cid] = paper_n

traces = sorted(TRACE_DIR.glob("ENG-THESIS-*.json"))
print(f"\n{'Case':<20} {'Rounds':<8} {'Top Topic Atoms (en)':<60} {'Papers':<8}")
print("="*100)
low_papers = []
for tp in traces:
    cid = tp.stem
    trace = json.loads(tp.read_text(encoding="utf-8"))
    topic = trace.get("topic", "")[:50]
    rounds_n = len(trace.get("rounds", []))
    paper_n = paper_counts.get(cid, -1)
    if paper_n < 5 and paper_n >= 0:
        low_papers.append((cid, paper_n))
    
    # Get sample queries from round 1
    r1 = trace.get("rounds", [{}])[0] 
    sample_q = [a.get("query", "") for a in r1.get("actions", [])[:2]]
    print(f"{cid:<20} {rounds_n:<8} {str(sample_q)[:60]:<60} {paper_n:<8}")

print(f"\n=== Cases with <5 papers ({len(low_papers)}) ===")
for cid, n in sorted(low_papers, key=lambda x: x[1]):
    print(f"  {cid}: {n} papers")

print(f"\n=== Paper distribution ===")
all_n = [paper_counts.get(tp.stem, -1) for tp in traces]
print(f"  Total: {len(all_n)}")
print(f"  With paper data: {sum(1 for n in all_n if n >= 0)}")
print(f"  Missing batch: {sum(1 for n in all_n if n == -1)}")
print(f"  Mean papers (w/ data): {sum(n for n in all_n if n >= 0) / max(1, sum(1 for n in all_n if n >= 0)):.1f}")
