"""Re2 Phase 3 E2E validation script."""
import os, sys, json
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

cases = [
    ('ENG-THESIS-074', '基于深度学习的混凝土桥梁裂缝检测研究'),
    ('ENG-THESIS-016', '基于深度学习的视觉SLAM语义地图的研究'),
    ('ENG-THESIS-046', '基于视觉的机械臂的目标检测和避障路径规划研究与应用'),
]

results = []
for cid, topic in cases:
    state_in = {
        'case_id': cid, 'topic': topic,
        'user_constraints': {'topic_zh': topic},
        'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
    }
    g = rg.build_graph()
    out = g.invoke(state_in, config={'configurable': {'thread_id': cid}})
    traces = out.get('trace_events') or []
    nodes = [t.get('node', '') for t in traces]
    feas = out.get('feasibility_report') or {}
    review = out.get('review_report') or {}
    inn = out.get('innovation_points') or []
    opt = out.get('optimization_directions') or {}
    rev_count = out.get('narrative_revision_count', 0)

    # Save state
    out_dir = Path('tmp_re2_eval') / cid
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'state.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    (out_dir / 'trace.json').write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    fv = feas.get('verdict', 'N/A')
    fs = feas.get('score', 'N/A')
    rv = review.get('overall_verdict', 'N/A')
    ni = len(inn)
    hf = bool(out.get('final_recommendation'))
    print(f'{cid}: {len(nodes)} nodes, rev_count={rev_count}, feas={fv}({fs}), review={rv}, n_innovation={ni}, has_final={hf}')

    # Check parallel timestamps
    inn_traces = [t for t in traces if t.get('node') == 'innovation_extractor']
    sot_traces = [t for t in traces if t.get('node') == 'sota_matcher']
    if inn_traces and sot_traces:
        inn_start = inn_traces[-1].get('started_at', '')
        sot_start = sot_traces[-1].get('started_at', '')
        print(f'  innovation started: {inn_start}, sota started: {sot_start}')

    # Check if optimization_paths reference parallel papers
    opt_paths = opt.get('optimization_paths', [])
    for p in opt_paths[:2]:
        ref = p.get('ref_parallel', '')
        direction = p.get('direction', '')
        print(f'  opt_path: direction={direction[:60]}, ref_parallel={ref[:60]}')

    results.append({
        'case_id': cid, 'n_nodes': len(nodes), 'rev_count': rev_count,
        'feas': fv, 'score': fs, 'review': rv,
    })

print()
print('Summary:')
for r in results:
    print(f'  {r}')
