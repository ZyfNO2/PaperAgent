"""Check innovation_points stitching_plan quality across Re2.1 cases."""
import json
from pathlib import Path

# Check 20-paper regression cases
eval_dir = Path('tmp_re21_eval/smoke_20')
heuristic_count = 0
llm_count = 0
empty_count = 0
total_inn = 0

for d in sorted(eval_dir.iterdir()):
    if not d.is_dir():
        continue
    sp = d / 'state.json'
    if not sp.exists():
        continue
    s = json.loads(sp.read_text(encoding='utf-8'))
    inn_points = s.get('innovation_points') or []
    if not inn_points:
        empty_count += 1
        continue

    # Check trace for innovation_extractor provider
    traces = s.get('trace_events') or []
    inn_traces = [t for t in traces if t.get('node') == 'innovation_extractor']
    prov = 'unknown'
    if inn_traces:
        prov = inn_traces[-1].get('provider', 'unknown')

    # Check stitching_plan quality
    for ip in inn_points[:2]:
        sp_field = ip.get('stitching_plan', '')
        desc = ip.get('description', '')[:60]
        baseline = ip.get('baseline_used', '')[:40]
        modules = ip.get('stitched_modules', [])
        total_inn += 1

        # Heuristic fallback signature: "待LLM生成" or very generic
        is_heuristic = ('待LLM' in sp_field or
                        sp_field == '' or
                        'heuristic' in str(ip).lower() or
                        desc.startswith('在') and '借鉴' in desc and len(desc) < 40)

        if is_heuristic or prov == 'heuristic':
            heuristic_count += 1
            tag = 'HEURISTIC'
        else:
            llm_count += 1
            tag = 'LLM'

        print(f'{d.name}: [{tag}] prov={prov}')
        print(f'  desc: {desc}')
        print(f'  baseline: {baseline}')
        print(f'  modules: {modules}')
        print(f'  stitching_plan: {sp_field[:120]}')
        print()

print('=== Summary ===')
print(f'Total innovation_points: {total_inn}')
print(f'LLM-generated: {llm_count}')
print(f'Heuristic fallback: {heuristic_count}')
print(f'Cases with 0 innovation: {empty_count}')
