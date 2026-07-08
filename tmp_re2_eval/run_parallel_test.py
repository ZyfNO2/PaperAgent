"""Re2 parallel test with a topic that finds more papers."""
import os, sys, json
os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')
from pathlib import Path
from apps.api.app.services.agents.graph import research_graph as rg

state_in = {
    'case_id': 're2-parallel-test',
    'topic': '基于YOLOv5的绝缘子检测与缺陷识别方法研究',
    'user_constraints': {'topic_zh': '基于YOLOv5的绝缘子检测与缺陷识别方法研究'},
    'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
}
g = rg.build_graph()
out = g.invoke(state_in, config={'configurable': {'thread_id': 're2-parallel-test'}})
traces = out.get('trace_events') or []
nodes = [t.get('node', '') for t in traces]
feas = out.get('feasibility_report') or {}
inn = out.get('innovation_points') or []
review = out.get('review_report') or {}
rev_count = out.get('narrative_revision_count', 0)

print(f'n_nodes: {len(nodes)}')
print(f'nodes: {nodes}')
fv = feas.get('verdict', 'N/A')
fs = feas.get('score', 'N/A')
print(f'feas: {fv}({fs})')
print(f'n_innovation: {len(inn)}')
rv = review.get('overall_verdict', 'N/A')
print(f'review: {rv}')
print(f'rev_count: {rev_count}')

# Check parallel
inn_t = [t for t in traces if t.get('node') == 'innovation_extractor']
sot_t = [t for t in traces if t.get('node') == 'sota_matcher']
if inn_t and sot_t:
    print(f'innovation: started={inn_t[-1].get("started_at", "")}, elapsed={inn_t[-1].get("elapsed_s", 0)}s')
    print(f'sota: started={sot_t[-1].get("started_at", "")}, elapsed={sot_t[-1].get("elapsed_s", 0)}s')

# Save
out_dir = Path('tmp_re2_eval/re2-parallel-test')
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / 'state.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
(out_dir / 'trace.json').write_text(
    json.dumps(traces, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print('State saved.')
