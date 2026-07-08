"""Gather model comparison data."""
import json

ds = json.loads(open('tmp_re15_eval/summary_deepseek.json', encoding='utf-8').read())
oc = json.loads(open('tmp_re15_eval/model_comparison/summary_opencode.json', encoding='utf-8').read())
sf = json.loads(open('tmp_re15_eval/model_comparison/summary_stepfun.json', encoding='utf-8').read())

print('=== DeepSeek ===')
for r in ds['results']:
    if r['case_id'] in ['ENG-THESIS-074', 'ENG-THESIS-016', 'ENG-THESIS-046']:
        cid = r['case_id']
        el = r['elapsed_s']
        np_ = r['n_papers']
        fv = r['feasibility_verdict']
        fs = r['feasibility_score']
        rv = r['review_verdict']
        print(f'  {cid}: {el}s, {np_} papers, feas={fv}({fs}), review={rv}')

print()
print('=== OpenCode ===')
for r in oc['results']:
    cid = r['case_id']
    el = r['elapsed_s']
    np_ = r['n_papers']
    fv = r['feasibility_verdict']
    fs = r['feasibility_score']
    rv = r['review_verdict']
    print(f'  {cid}: {el}s, {np_} papers, feas={fv}({fs}), review={rv}')

print()
print('=== StepFun ===')
for r in sf['results']:
    cid = r['case_id']
    el = r['elapsed_s']
    np_ = r['n_papers']
    fv = r['feasibility_verdict']
    fs = r['feasibility_score']
    rv = r['review_verdict']
    print(f'  {cid}: {el}s, {np_} papers, feas={fv}({fs}), review={rv}')

# Self-test summary
st = json.loads(open('tmp_re15_eval/self_test_report.json', encoding='utf-8').read())
print()
print('=== Self-test ===')
print(f"  e2e: {sum(1 for c in st['per_case'] if c.get('e2e_completeness',{}).get('pass'))}/{st['n_cases']}")
print(f"  auth: {sum(1 for c in st['per_case'] if c.get('paper_authenticity',{}).get('pass'))}/{st['n_cases']}")
print(f"  rel: {sum(1 for c in st['per_case'] if c.get('topic_relevance',{}).get('pass'))}/{st['n_cases']}")
print(f"  feas_div: {'pass' if st['feasibility_diversity'].get('pass') else 'fail'}")
