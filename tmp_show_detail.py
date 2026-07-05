"""Show detailed dropped and verified items."""
import json, sys

case = sys.argv[1] if len(sys.argv) > 1 else "re13-steel-yolov5"
with open(f"tmp_re13_eval/{case}/state.json", encoding="utf-8") as f:
    st = json.load(f)

fr = st.get("filter_results") or {}
print("=== ALL dropped items ===")
for d in fr.get("dropped_items", []):
    print(f"  title: {d.get('title','')[:80]}")
    print(f"  reason: {d.get('reason','')[:150]}")
    print()

print("=== verified_papers full ===")
for p in st.get("verified_papers", []):
    print(f"  title: {p.get('title','')[:80]}")
    print(f"  verdict: {p.get('verdict','')} | relation: {p.get('relation_to_topic','')}")
    print(f"  hit: {p.get('hit_keywords',[])}")
    print(f"  reason: {p.get('reason','')[:200]}")
    print()

# Show paper_candidates that were kept by quality_filter (before verify)
pc = st.get("paper_candidates") or []
print(f"=== paper_candidates after quality_filter ({len(pc)}) ===")
for i, p in enumerate(pc):
    print(f"  [{i:2d}] {p.get('title','')[:80]} | source={p.get('source','')}")
