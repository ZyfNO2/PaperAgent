import json
with open('tmp_re04_eval/re10_fix3_typical_case3/traces/TYPICAL-01.json', 'r', encoding='utf-8') as f:
    t = json.load(f)
print(f"topic: {t.get('topic', '')}")
for r in t.get('rounds', []):
    queries = [a.get('query', '') for a in r.get('actions', [])]
    has_fallback = any('[Fallback]' in q for q in queries)
    has_steel = any('steel' in q.lower() for q in queries)
    print(f"Round {r['round']}: {len(queries)} queries, fallback={has_fallback}, steel_contam={has_steel}")
    for q in queries:
        print(f"  - {q}")
