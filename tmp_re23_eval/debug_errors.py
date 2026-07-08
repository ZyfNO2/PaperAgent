"""Debug why crossref/github return 0 — check error details."""
import json

for vid in ['V-SLAM', 'V-CRACK', 'V-MED']:
    s = json.loads(open(f'tmp_re23_eval/{vid}/state.json', encoding='utf-8').read())
    traces = s.get('trace_events') or []
    for t in traces:
        if t.get('node') in ('retrieve', 'paper_retriever'):
            tools = t.get('tool_calls', [])
            errors = t.get('errors', [])
            print(f"{vid}:")
            print(f"  tool_calls: {tools}")
            print(f"  errors: {errors[:3]}")
            break
