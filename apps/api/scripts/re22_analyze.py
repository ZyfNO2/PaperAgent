"""Re2.2 statistical analysis — domain x difficulty x edge case matrix.

Usage:
    python apps/api/scripts/re22_analyze.py --dir tmp_re22_eval/all_100
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_states(eval_dir):
    states = []
    for d in sorted(Path(eval_dir).iterdir()):
        if not d.is_dir():
            continue
        sp = d / 'state.json'
        if not sp.exists():
            continue
        try:
            s = json.loads(sp.read_text(encoding='utf-8'))
            s['_case_dir'] = str(d)
            states.append(s)
        except Exception:
            pass
    return states


def analyze(states, summary):
    """Produce domain matrix, difficulty matrix, edge cases, consistency check."""
    # Build lookup from summary for domain/difficulty
    meta = {r['case_id']: r for r in summary.get('results', [])}

    # Domain matrix
    domain_data = defaultdict(lambda: {
        'n': 0, 'n_completed': 0, 'accept_counts': [], 'scores': [],
        'feas_verdicts': defaultdict(int), 'review_verdicts': defaultdict(int),
        'innovation_count': 0, 'n_zero_accept': 0,
    })
    # Difficulty matrix
    diff_data = defaultdict(lambda: {
        'n': 0, 'n_completed': 0, 'accept_counts': [], 'scores': [],
        'innovation_count': 0, 'block_count': 0,
    })

    edge = {
        'graph_not_completed': [],
        'zero_verified': [],
        'zero_innovation': [],
        'review_accepted': [],
        'feasibility_feasible': [],
        'high_difficulty_with_innovation': [],
    }

    for s in states:
        cid = s.get('case_id', '')
        m = meta.get(cid, {})
        domain = m.get('domain', 'unknown')
        difficulty = m.get('difficulty', 'unknown')

        n_papers = len(s.get('verified_papers') or [])
        has_final = bool(s.get('final_recommendation'))
        feas = s.get('feasibility_report') or {}
        review = s.get('review_report') or {}
        n_inn = len(s.get('innovation_points') or [])
        score = feas.get('score', 0)
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 0

        # Domain
        dd = domain_data[domain]
        dd['n'] += 1
        if has_final:
            dd['n_completed'] += 1
        dd['accept_counts'].append(n_papers)
        dd['scores'].append(score)
        dd['feas_verdicts'][feas.get('verdict', '')] += 1
        dd['review_verdicts'][review.get('overall_verdict', '')] += 1
        if n_inn > 0:
            dd['innovation_count'] += 1
        if n_papers == 0:
            dd['n_zero_accept'] += 1

        # Difficulty
        df = diff_data[difficulty]
        df['n'] += 1
        if has_final:
            df['n_completed'] += 1
        df['accept_counts'].append(n_papers)
        df['scores'].append(score)
        if n_inn > 0:
            df['innovation_count'] += 1
        if review.get('overall_verdict') == 'BLOCK':
            df['block_count'] += 1

        # Edge cases
        if not has_final:
            edge['graph_not_completed'].append(cid)
        if n_papers == 0:
            edge['zero_verified'].append(cid)
        if n_inn == 0 and has_final:
            edge['zero_innovation'].append(cid)
        if review.get('overall_verdict') == 'ACCEPT':
            edge['review_accepted'].append(cid)
        if feas.get('verdict') == 'feasible':
            edge['feasibility_feasible'].append(cid)
        if difficulty == '高' and n_inn > 0:
            edge['high_difficulty_with_innovation'].append(cid)

    # Normalize domain matrix
    domain_out = {}
    for domain, dd in sorted(domain_data.items()):
        domain_out[domain] = {
            'n': dd['n'],
            'completion_rate': round(dd['n_completed'] / dd['n'], 2) if dd['n'] else 0,
            'avg_accept': round(sum(dd['accept_counts']) / len(dd['accept_counts']), 1) if dd['accept_counts'] else 0,
            'avg_score': round(sum(dd['scores']) / len(dd['scores']), 1) if dd['scores'] else 0,
            'feasibility_verdicts': dict(dd['feas_verdicts']),
            'review_verdicts': dict(dd['review_verdicts']),
            'innovation_rate': round(dd['innovation_count'] / dd['n'], 2) if dd['n'] else 0,
            'n_zero_accept': dd['n_zero_accept'],
        }

    # Normalize difficulty matrix
    diff_out = {}
    for diff, df in sorted(diff_data.items()):
        diff_out[diff] = {
            'n': df['n'],
            'avg_accept': round(sum(df['accept_counts']) / len(df['accept_counts']), 1) if df['accept_counts'] else 0,
            'avg_score': round(sum(df['scores']) / len(df['scores']), 1) if df['scores'] else 0,
            'innovation_rate': round(df['innovation_count'] / df['n'], 2) if df['n'] else 0,
            'block_rate': round(df['block_count'] / df['n'], 2) if df['n'] else 0,
        }

    # Consistency check with Re2.1 smoke_20
    re21_path = Path('tmp_re21_eval/smoke_20/summary_deepseek.json')
    consistency = {'n_common': 0, 'feasibility_consistent': 0, 'review_consistent': 0,
                    'innovation_consistent': 0, 'inconsistency_cases': []}
    if re21_path.exists():
        re21 = json.loads(re21_path.read_text(encoding='utf-8')).get('results', [])
        re21_map = {r['case_id']: r for r in re21}
        re22_map = {r['case_id']: r for r in summary.get('results', [])}
        common = set(re21_map.keys()) & set(re22_map.keys())
        consistency['n_common'] = len(common)
        for cid in sorted(common):
            o = re21_map[cid]
            n = re22_map[cid]
            o_feas = o.get('feasibility_verdict', '')
            n_feas = n.get('feasibility_verdict', '')
            o_rev = o.get('review_verdict', '')
            n_rev = n.get('review_verdict', '')
            o_inn = (o.get('n_innovation', 0) or 0) > 0
            n_inn = (n.get('n_innovation', 0) or 0) > 0

            if o_feas == n_feas:
                consistency['feasibility_consistent'] += 1
            if o_rev == n_rev:
                consistency['review_consistent'] += 1
            if o_inn == n_inn:
                consistency['innovation_consistent'] += 1
            if o_feas != n_feas or o_rev != n_rev:
                consistency['inconsistency_cases'].append({
                    'case_id': cid,
                    're21_feasibility': o_feas,
                    're22_feasibility': n_feas,
                    're21_review': o_rev,
                    're22_review': n_rev,
                })

    return {
        'n_cases': len(states),
        'n_completed': sum(1 for s in states if s.get('final_recommendation')),
        'domain_matrix': domain_out,
        'difficulty_matrix': diff_out,
        'edge_cases': edge,
        'consistency_check': consistency,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default='tmp_re22_eval/all_100')
    args = parser.parse_args()

    eval_dir = Path(args.dir)
    if not eval_dir.exists():
        print(f"ERROR: {eval_dir} not found")
        return

    states = load_states(eval_dir)
    print(f"Loaded {len(states)} case states")

    summary_path = eval_dir / 'summary_deepseek.json'
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding='utf-8'))

    result = analyze(states, summary)

    out_path = Path('tmp_re22_eval/analysis.json')
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print("\n=== Analysis ===")
    print(f"Cases: {result['n_cases']}, Completed: {result['n_completed']}")
    print("\nDomain matrix:")
    for d, dd in result['domain_matrix'].items():
        print(f"  {d}: n={dd['n']}, avg_accept={dd['avg_accept']}, innovation={dd['innovation_rate']}")
    print("\nDifficulty matrix:")
    for d, dd in result['difficulty_matrix'].items():
        print(f"  {d}: n={dd['n']}, avg_accept={dd['avg_accept']}, block_rate={dd['block_rate']}")
    print("\nEdge cases:")
    for k, v in result['edge_cases'].items():
        print(f"  {k}: {len(v)}")
    print("\nConsistency:")
    c = result['consistency_check']
    print(f"  common: {c['n_common']}, feas: {c['feasibility_consistent']}, review: {c['review_consistent']}")
    print(f"\nSaved to: {out_path}")


if __name__ == '__main__':
    main()
