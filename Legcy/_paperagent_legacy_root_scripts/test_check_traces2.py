import json

for cid in ['TYPICAL-01', 'TYPICAL-02', 'TYPICAL-03']:
    try:
        with open(f'tmp_re04_eval/re10_fix3_typical_cases_v2/traces/{cid}.json', 'r', encoding='utf-8') as f:
            trace = json.load(f)
    except FileNotFoundError:
        print(f"{cid}: trace not found")
        continue
    print(f"\n=== {cid} topic: {trace.get('topic', '')} ===")
    for i, r in enumerate(trace.get('rounds', [])):
        actions = r.get('actions', [])
        print(f"  Round {i+1}: {len(actions)} actions")
        for a in actions:
            q = a.get('query', '')
            why = a.get('why', '')
            print(f"    Q: {q}")
            if why:
                print(f"    W: {why}")
