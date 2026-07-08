"""Analyze Phase 1 verification results."""
import json, os

data = json.loads(open('tmp_re21_eval/verify/verify_20260706_075256_phase1-s2.json', encoding='utf-8').read())

# Check: did S2 appear in retrieve tools?
# The verify script captures retrieve_tools from trace tool_calls
# But those are the tools that returned results, not all attempted tools
# Let's check the raw_results in state files

for vid in ['V-MED', 'V-SLAM', 'V-CRACK']:
    s = json.loads(open(f'tmp_re21_eval/{vid}/state.json', encoding='utf-8').read())
    raw = s.get('raw_results', {})
    raw_keys = list(raw.keys()) if isinstance(raw, dict) else []
    n_candidates = len(s.get('paper_candidates', []))
    n_verified = len(s.get('verified_papers', []))
    n_weak = len(s.get('weak_papers', []))
    tools_in_trace = data[vid].get('retrieve_tools', [])

    print(f'{vid}:')
    print(f'  raw_results keys: {raw_keys}')
    print(f'  tools in trace: {tools_in_trace}')
    print(f'  n_candidates: {n_candidates}')
    print(f'  n_verified: {n_verified}, n_weak: {n_weak}')
    print(f'  has_s2: {"semantic_scholar" in raw_keys}')
    print()

# Compare with Re1.5 baseline
print('=== Re1.5 baseline comparison ===')
re15_dir = 'tmp_re15_eval/smoke_20'
for vid, re15_id in [('V-MED', 're2-innovation-test'), ('V-SLAM', 'ENG-THESIS-016'), ('V-CRACK', 'ENG-THESIS-074')]:
    re15_path = f'{re15_dir}/{re15_id}/state.json'
    if not os.path.exists(re15_path):
        re15_path = f'tmp_re2_eval/{re15_id}/state.json'
    if os.path.exists(re15_path):
        s15 = json.loads(open(re15_path, encoding='utf-8').read())
        n15 = len(s15.get('paper_candidates', []))
        v15 = len(s15.get('verified_papers', []))
        print(f'{vid} (Re1.5/Re2): candidates={n15}, verified={v15}')
    else:
        print(f'{vid}: no baseline found')
