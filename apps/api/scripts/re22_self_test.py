"""Re2.2 self-test — run 4 validators on all 100 cases.

Usage:
    python apps/api/scripts/re22_self_test.py --dir tmp_re22_eval/all_100
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tests.self_test.e2e_completeness_validator import validate as validate_e2e
from tests.self_test.paper_authenticity_validator import validate as validate_auth
from tests.self_test.topic_relevance_validator import validate as validate_rel
from tests.self_test.feasibility_diversity_validator import validate_batch as validate_feas_div


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default='tmp_re22_eval/all_100')
    args = parser.parse_args()

    eval_path = Path(args.dir)
    states = []
    case_ids = []

    for d in sorted(eval_path.iterdir()):
        if not d.is_dir():
            continue
        sp = d / 'state.json'
        if not sp.exists():
            continue
        try:
            s = json.loads(sp.read_text(encoding='utf-8'))
            states.append(s)
            case_ids.append(s.get('case_id', d.name))
        except Exception:
            pass

    print(f"Loaded {len(states)} cases")

    per_case = []
    for cid, state in zip(case_ids, states):
        result = {
            'case_id': cid,
            'e2e_completeness': validate_e2e(state),
            'paper_authenticity': validate_auth(state),
            'topic_relevance': validate_rel(state),
        }
        per_case.append(result)

    feas_div = validate_feas_div(states) if len(states) > 1 else {'pass': False}

    n_e2e = sum(1 for c in per_case if c.get('e2e_completeness', {}).get('pass'))
    n_auth = sum(1 for c in per_case if c.get('paper_authenticity', {}).get('pass'))
    n_rel = sum(1 for c in per_case if c.get('topic_relevance', {}).get('pass'))

    report = {
        'n_cases': len(states),
        'e2e_completeness_pass': n_e2e,
        'paper_authenticity_pass': n_auth,
        'topic_relevance_pass': n_rel,
        'feasibility_diversity': feas_div,
        'per_case': per_case,
    }

    out_path = Path('tmp_re22_eval/self_test_report.json')
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    print(f"\n=== Self-test Results ===")
    print(f"e2e_completeness: {n_e2e}/{len(states)}")
    print(f"paper_authenticity: {n_auth}/{len(states)}")
    print(f"topic_relevance: {n_rel}/{len(states)}")
    print(f"feasibility_diversity: {'pass' if feas_div.get('pass') else 'fail'}")
    print(f"\nSaved to: {out_path}")


if __name__ == '__main__':
    main()
