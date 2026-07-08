"""Generate summary JSON from existing state files."""
import json
from pathlib import Path

eval_dir = Path('tmp_re15_eval/smoke_20')
results = []
for d in sorted(eval_dir.iterdir()):
    if not d.is_dir():
        continue
    sp = d / 'state.json'
    if not sp.exists():
        continue
    s = json.loads(sp.read_text(encoding='utf-8'))
    feas = s.get('feasibility_report') or {}
    review = s.get('review_report') or {}
    results.append({
        'case_id': s.get('case_id', d.name),
        'topic': s.get('topic', ''),
        'status': 'done',
        'elapsed_s': s.get('elapsed_s', 0),
        'n_papers': len(s.get('verified_papers') or []),
        'n_weak': len(s.get('weak_papers') or []),
        'n_nodes': len(s.get('trace_events') or []),
        'n_packages': len(s.get('work_packages') or []),
        'feasibility_verdict': feas.get('verdict', ''),
        'feasibility_score': feas.get('score', 0),
        'review_verdict': review.get('overall_verdict', ''),
        'has_final': bool(s.get('final_recommendation')),
    })

n_done = sum(1 for r in results if r['status'] == 'done')
n_has_final = sum(1 for r in results if r.get('has_final'))
summary = {
    'provider': 'deepseek',
    'n_cases': len(results),
    'n_done': n_done,
    'n_error': 0,
    'n_has_final': n_has_final,
    'results': results,
}
Path('tmp_re15_eval').mkdir(exist_ok=True)
Path('tmp_re15_eval/summary_deepseek.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, default=str),
    encoding='utf-8',
)
print(f'Generated summary: {len(results)} cases, {n_done} done, {n_has_final} has_final')
for r in results:
    cid = r['case_id']
    el = r['elapsed_s']
    np_ = r['n_papers']
    nn = r['n_nodes']
    fv = r['feasibility_verdict']
    fs = r['feasibility_score']
    rv = r['review_verdict']
    hf = r['has_final']
    print(f'  {cid}: {el}s, {np_} papers, {nn} nodes, feas={fv}({fs}), review={rv}, final={hf}')
