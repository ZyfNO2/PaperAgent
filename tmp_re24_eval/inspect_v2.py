import json
from pathlib import Path
st = json.loads(Path('tmp_re13_eval/re24-screenshot-v2/state.json').read_text(encoding='utf-8'))
raw = st.get('raw_results', {})
print('raw:', {k: len(v) for k, v in raw.items() if isinstance(v, list)})
traces = st.get('trace_events') or []
for t in traces:
    node = t.get('node', '?')
    out = t.get('output_summary', {})
    errs = t.get('errors', [])
    print(f'  {node:30s} {out}  errors={errs}')
