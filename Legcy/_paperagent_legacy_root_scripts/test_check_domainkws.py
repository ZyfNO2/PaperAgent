import json

for cid in ['TYPICAL-01', 'TYPICAL-02', 'TYPICAL-03']:
    try:
        with open(f'tmp_re04_eval/re10_fix3_typical_cases_v2/traces/{cid}.json', 'r', encoding='utf-8') as f:
            trace = json.load(f)
    except FileNotFoundError:
        print(f"{cid}: trace not found")
        continue
    print(f"\n=== {cid} ===")
    for i, r in enumerate(trace.get('rounds', [])):
        obs = r.get('observations', {})
        scout = obs.get('domain_scout', {})
        if scout:
            dk = scout.get('domain_keywords', {})
            print(f"  Round {i+1} domain_kws en: {dk.get('en', [])[:5]}")
            print(f"  Round {i+1} domain_kws method: {dk.get('method', [])[:5]}")
            print(f"  Round {i+1} domain_kws object: {dk.get('object', [])[:5]}")
            print(f"  Round {i+1} domain_kws task: {dk.get('task', [])[:5]}")
            print(f"  Round {i+1} search_notes: {scout.get('search_notes', '')[:100]}")
            break
