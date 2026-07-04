import json

for cid in ['TYPICAL-01', 'TYPICAL-02', 'TYPICAL-03']:
    try:
        with open(f'tmp_re04_eval/re10_fix3_typical_cases_v2/traces/{cid}.json', 'r', encoding='utf-8') as f:
            trace = json.load(f)
    except FileNotFoundError:
        print(f"{cid}: trace not found")
        continue
    rounds = trace.get('rounds', [])
    print(f"\n=== {cid} ({len(rounds)} rounds) ===")
    for i, r in enumerate(rounds):
        queries = r.get('executed_queries', [])
        all_q = ' '.join(q.get('query', '') for q in queries)
        has_steel = 'steel' in all_q.lower()
        has_surface = 'surface defect' in all_q.lower()
        has_fallback = '[Fallback]' in all_q
        status = 'OK'
        if has_steel or has_surface:
            status = 'CONTAMINATED'
        print(f"  Round {i+1}: {len(queries)} queries, status={status}, fallback={has_fallback}")
        for q in queries:
            print(f"    - {q.get('query', '')[:100]}")
