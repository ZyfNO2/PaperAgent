"""Debug comparison field access."""
import json

old = json.loads(open('tmp_re15_eval/summary_deepseek.json', encoding='utf-8').read()).get('results', [])
old_map = {r['case_id']: r for r in old}
new = json.loads(open('tmp_re21_eval/smoke_20/summary_deepseek.json', encoding='utf-8').read()).get('results', [])
new_map = {r['case_id']: r for r in new}

common = set(old_map.keys()) & set(new_map.keys())
print(f"old keys: {list(old_map.keys())[:3]}")
print(f"new keys: {list(new_map.keys())[:3]}")
print(f"common: {len(common)}")

for cid in ['ENG-THESIS-015', 'ENG-THESIS-016']:
    o = old_map.get(cid, {})
    n = new_map.get(cid, {})
    print(f"\n{cid}:")
    print(f"  old: n_papers={o.get('n_papers')}, review={o.get('review_verdict')}, score={o.get('feasibility_score')}")
    print(f"  new: n_papers={n.get('n_papers')}, review={n.get('review_verdict')}, score={n.get('feasibility_score')}")

# Check if case_id keys match exactly
old_ids = set(old_map.keys())
new_ids = set(new_map.keys())
print(f"\nIn old but not new: {old_ids - new_ids}")
print(f"In new but not old: {new_ids - old_ids}")
