"""Test innovation chain with a topic that historically finds lots of papers."""
import os, sys, json
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

# This topic had 9 accept in Re1.3
topic = '基于大语言模型的医学问答可信度评估方法研究'
state_in = {
    'case_id': 're2-innovation-test',
    'topic': topic,
    'user_constraints': {'topic_zh': topic},
    'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
}
g = rg.build_graph()
out = g.invoke(state_in, config={'configurable': {'thread_id': 're2-innovation-test'}})
traces = out.get('trace_events') or []
nodes = [t.get('node', '') for t in traces]
feas = out.get('feasibility_report') or {}
inn = out.get('innovation_points') or []
sota = out.get('sota_comparison') or {}
narr = out.get('research_narratives') or {}
opt = out.get('optimization_directions') or {}
review = out.get('review_report') or {}

print(f'n_nodes: {len(nodes)}')
print(f'nodes: {nodes}')
fv = feas.get('verdict', 'N/A')
fs = feas.get('score', 'N/A')
print(f'feasibility: {fv}({fs})')
print(f'n_verified: {len(out.get("verified_papers", []))}')
print(f'n_baseline: {len(out.get("baseline_candidates", []))}')
print(f'n_parallel: {len(out.get("parallel_candidates", []))}')
print(f'n_innovation: {len(inn)}')
if inn:
    for i in inn[:2]:
        desc = i.get('description', '')[:80]
        baseline = i.get('baseline_used', '')[:60]
        print(f'  innovation: {desc}')
        print(f'    baseline_used: {baseline}')
print(f'sota comparison_papers: {len(sota.get("comparison_papers", []))}')
print(f'narrative nick_model: {narr.get("nick_model_name", "N/A")}')
three_p = narr.get('three_problems', [])
if three_p:
    for p in three_p[:2]:
        prob = p.get('problem', '')[:60]
        from_p = p.get('from_paper', '')[:60]
        print(f'  problem: {prob}')
        print(f'    from_paper: {from_p}')
print(f'opt n_paths: {len(opt.get("optimization_paths", []))}')
for p in opt.get('optimization_paths', [])[:1]:
    ref = p.get('ref_parallel', '')[:80]
    direction = p.get('direction', '')[:80]
    print(f'  opt: direction={direction}')
    print(f'    ref_parallel={ref}')
rv = review.get('overall_verdict', 'N/A')
print(f'review: {rv}')
print(f'rev_count: {out.get("narrative_revision_count", 0)}')
print(f'has_final: {bool(out.get("final_recommendation"))}')

# Check parallel timestamps
inn_t = [t for t in traces if t.get('node') == 'innovation_extractor']
sot_t = [t for t in traces if t.get('node') == 'sota_matcher']
if inn_t and sot_t:
    print(f'\nParallel check:')
    print(f'  innovation: started={inn_t[-1].get("started_at", "")}, elapsed={inn_t[-1].get("elapsed_s", 0)}s')
    print(f'  sota: started={sot_t[-1].get("started_at", "")}, elapsed={sot_t[-1].get("elapsed_s", 0)}s')

# Save
out_dir = Path('tmp_re2_eval/re2-innovation-test')
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / 'state.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
(out_dir / 'trace.json').write_text(
    json.dumps(traces, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print('\nState saved.')
