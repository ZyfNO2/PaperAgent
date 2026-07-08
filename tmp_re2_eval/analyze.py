"""Analyze Re2 E2E results."""
import json

for cid in ['ENG-THESIS-074', 'ENG-THESIS-016', 'ENG-THESIS-046']:
    s = json.loads(open(f'tmp_re2_eval/{cid}/state.json', encoding='utf-8').read())
    feas = s.get('feasibility_report') or {}
    inn = s.get('innovation_points') or []
    opt = s.get('optimization_directions') or {}
    paths = opt.get('optimization_paths', [])
    traces = s.get('trace_events') or []
    nodes = [t.get('node', '') for t in traces]

    inn_t = [t for t in traces if t.get('node') == 'innovation_extractor']
    sot_t = [t for t in traces if t.get('node') == 'sota_matcher']
    inn_start = inn_t[-1].get('started_at', '') if inn_t else ''
    sot_start = sot_t[-1].get('started_at', '') if sot_t else ''
    inn_el = inn_t[-1].get('elapsed_s', 0) if inn_t else 0
    sot_el = sot_t[-1].get('elapsed_s', 0) if sot_t else 0

    reason = feas.get('reason', '')[:120]
    print(f'{cid}:')
    print(f'  feas_reason: {reason}')
    print(f'  n_innovation: {len(inn)}')
    print(f'  n_opt_paths: {len(paths)}')
    for p in paths[:2]:
        ref = p.get('ref_parallel', '')[:80]
        direction = p.get('direction', '')[:60]
        print(f'    direction: {direction}')
        print(f'    ref_parallel: {ref}')
    print(f'  innovation started: {inn_start}, elapsed: {inn_el}s')
    print(f'  sota started: {sot_start}, elapsed: {sot_el}s')

    devils = [n for n in nodes if n == 'devils_advocate']
    opt_nodes = [n for n in nodes if n == 'optimization_advisor']
    narr = [n for n in nodes if n == 'narrative_builder']
    print(f'  devils: {len(devils)}, optimization: {len(opt_nodes)}, narrative: {len(narr)}')
    print(f'  rev_count: {s.get("narrative_revision_count", 0)}')
    print()
