"""Check if S2 returned any results in the verification runs."""
import json

for vid in ['V-MED', 'V-SLAM', 'V-CRACK']:
    s = json.loads(open(f'tmp_re21_eval/{vid}/state.json', encoding='utf-8').read())
    raw = s.get('raw_results', {})
    if isinstance(raw, dict):
        keys = list(raw.keys())
        s2_count = len(raw.get('semantic_scholar', []))
    else:
        keys = []
        s2_count = 0
    n_cand = len(s.get('paper_candidates', []))
    print(f'{vid}: raw_keys={keys}, s2_hits={s2_count}, candidates={n_cand}')
