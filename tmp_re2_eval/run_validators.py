"""Run validators on Re2 E2E cases."""
import sys, json
sys.path.insert(0, r'G:\PaperAgent')
from tests.self_test.e2e_completeness_validator import validate as validate_e2e
from tests.self_test.paper_authenticity_validator import validate as validate_auth
from tests.self_test.topic_relevance_validator import validate as validate_rel
from tests.self_test.feasibility_diversity_validator import validate_batch as validate_feas_div

states = []
for cid in ['ENG-THESIS-074', 'ENG-THESIS-016', 'ENG-THESIS-046']:
    s = json.loads(open(f'tmp_re2_eval/{cid}/state.json', encoding='utf-8').read())
    states.append(s)
    e2e = validate_e2e(s)
    auth = validate_auth(s)
    rel = validate_rel(s)
    print(f'{cid}:')
    print(f'  e2e: pass={e2e["pass"]}, n_found={e2e["n_found"]}, missing={e2e["missing_nodes"][:5]}')
    print(f'  auth: pass={auth["pass"]}, n_checked={auth["n_checked"]}')
    print(f'  rel: pass={rel["pass"]}, rate={rel["relevance_rate"]}')

feas_div = validate_feas_div(states)
print(f'\nfeasibility_diversity: pass={feas_div["pass"]}')
print(f'  verdicts: {feas_div["unique_verdicts"]}')
print(f'  score_min: {feas_div["score_min"]}, score_max: {feas_div["score_max"]}, spread: {feas_div["score_spread"]}')
