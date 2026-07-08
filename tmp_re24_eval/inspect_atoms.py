import json
from pathlib import Path
st = json.loads(Path('tmp_re13_eval/re24-debug-direct/state.json').read_text(encoding='utf-8'))
atoms = st.get('topic_atoms') or {}
print('topic_atoms:', atoms)
print('search_plan:', st.get('search_plan'))
