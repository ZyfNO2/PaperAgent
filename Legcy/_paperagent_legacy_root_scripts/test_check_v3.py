import json

for cid in ['TYPICAL-01', 'TYPICAL-02']:
    with open(f'tmp_re04_eval/re10_fix3_typical_cases_v3/traces/{cid}.json', 'r', encoding='utf-8') as f:
        t = json.load(f)
    print(f"\n=== {cid}: {t.get('topic', '')} ===")
    for r in t.get('rounds', []):
        queries = [a.get('query', '') for a in r.get('actions', [])]
        has_fallback = any('[Fallback]' in q for q in queries)
        print(f"  Round {r['round']}: {len(queries)} queries, fallback={has_fallback}")
        for q in queries:
            print(f"    - {q}")
