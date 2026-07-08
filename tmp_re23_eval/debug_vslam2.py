"""Check raw_results and trace errors for V-SLAM."""
import json
s = json.loads(open('tmp_re23_eval/V-SLAM/state.json', encoding='utf-8').read())
raw = s.get('raw_results', {})
print("raw_results keys:", list(raw.keys()) if isinstance(raw, dict) else type(raw))
if isinstance(raw, dict):
    for k, v in raw.items():
        print(f"  {k}: {len(v)} items")

# Check all trace events
traces = s.get('trace_events') or []
for t in traces:
    node = t.get('node', '')
    if node in ('retrieve', 'paper_retriever', 'quality_filter', 'verify'):
        out = t.get('output_summary', {})
        tc = t.get('tool_calls', [])
        errs = t.get('errors', [])
        print(f"\n{node}:")
        print(f"  output: {out}")
        print(f"  tool_calls: {tc}")
        print(f"  errors: {errs}")
