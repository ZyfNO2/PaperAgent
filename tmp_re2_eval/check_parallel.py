"""Check parallel test results."""
import json

s = json.loads(open('tmp_re2_eval/re2-parallel-test/state.json', encoding='utf-8').read())
traces = s.get('trace_events') or []
for t in traces:
    node = t.get('node', '')
    if node in ('innovation_extractor', 'sota_matcher', 'work_package', 'narrative_builder'):
        started = t.get('started_at', '')
        elapsed = t.get('elapsed_s', 0)
        print(f'{node}: started={started}, elapsed={elapsed}s')

feas = s.get('feasibility_report') or {}
print(f'feas: {feas.get("verdict")}({feas.get("score")})')
print(f'n_baseline: {len(s.get("baseline_candidates", []))}')
print(f'n_parallel: {len(s.get("parallel_candidates", []))}')
print(f'n_verified: {len(s.get("verified_papers", []))}')
