"""Re2.1 comparison script — compare Re1.5 vs Re2.1 results."""
import argparse
import json
from pathlib import Path


def load_summary(eval_dir):
    """Load summary JSON or build from state files."""
    def _normalize(r):
        """Normalize field names across summary versions."""
        return {
            'case_id': r.get('case_id', ''),
            'n_papers': r.get('n_papers') or r.get('n_verified') or 0,
            'feasibility_verdict': r.get('feasibility_verdict', ''),
            'feasibility_score': r.get('feasibility_score', 0),
            'review_verdict': r.get('review_verdict', ''),
            'has_final': r.get('has_final', False),
        }

    # Try subdir summary first, then parent dir summary
    for d in [Path(eval_dir), Path(eval_dir).parent]:
        sp = d / 'summary_deepseek.json'
        if sp.exists():
            results = [_normalize(r) for r in json.loads(sp.read_text(encoding='utf-8')).get('results', [])]
            # Only use if review_verdict is non-empty for at least some cases
            if any(r['review_verdict'] for r in results):
                return results
    # Build from state files
    results = []
    for d in sorted(Path(eval_dir).iterdir()):
        if not d.is_dir():
            continue
        sf = d / 'state.json'
        if not sf.exists():
            continue
        s = json.loads(sf.read_text(encoding='utf-8'))
        feas = s.get('feasibility_report') or {}
        review = s.get('review_report') or {}
        results.append({
            'case_id': s.get('case_id', d.name),
            'n_papers': len(s.get('verified_papers') or []),
            'feasibility_verdict': feas.get('verdict', ''),
            'feasibility_score': feas.get('score', 0),
            'review_verdict': review.get('overall_verdict', ''),
            'has_final': bool(s.get('final_recommendation')),
        })
    return results


def compare(old_dir, new_dir):
    old = load_summary(old_dir)
    new = load_summary(new_dir)

    old_map = {r['case_id']: r for r in old}
    new_map = {r['case_id']: r for r in new}

    def _safe_int(v):
        try: return int(v)
        except (ValueError, TypeError): return 0

    common = set(old_map.keys()) & set(new_map.keys())

    old_accepts = [old_map[c].get('n_papers', 0) for c in common]
    new_accepts = [new_map[c].get('n_papers', 0) for c in common]

    old_nr = sum(1 for c in common if old_map[c].get('feasibility_verdict') == 'not_recommended')
    new_nr = sum(1 for c in common if new_map[c].get('feasibility_verdict') == 'not_recommended')

    old_block = sum(1 for c in common if old_map[c].get('review_verdict') == 'BLOCK')
    new_block = sum(1 for c in common if new_map[c].get('review_verdict') == 'BLOCK')

    improved = 0
    regressed = 0
    for c in common:
        o = old_map[c]
        n = new_map[c]
        # Improvement: more papers OR better feasibility OR better review
        if n.get('n_papers', 0) > o.get('n_papers', 0):
            improved += 1
        elif _safe_int(n.get('feasibility_score', 0)) > _safe_int(o.get('feasibility_score', 0)):
            improved += 1
        elif o.get('review_verdict') == 'BLOCK' and n.get('review_verdict') != 'BLOCK':
            improved += 1
        # Regression: fewer papers OR worse feasibility
        if n.get('n_papers', 0) < o.get('n_papers', 0):
            regressed += 1
        elif _safe_int(n.get('feasibility_score', 0)) < _safe_int(o.get('feasibility_score', 0)):
            regressed += 1

    old_avg = round(sum(old_accepts) / len(old_accepts), 1) if old_accepts else 0
    new_avg = round(sum(new_accepts) / len(new_accepts), 1) if new_accepts else 0

    return {
        'n_common': len(common),
        'old_avg_accept': old_avg,
        'new_avg_accept': new_avg,
        'old_not_recommended': old_nr,
        'new_not_recommended': new_nr,
        'old_block': old_block,
        'new_block': new_block,
        'cases_improved': improved,
        'cases_regressed': regressed,
        'per_case': {
            c: {
                'old_papers': old_map[c].get('n_papers', 0),
                'new_papers': new_map[c].get('n_papers', 0),
                'old_feas': old_map[c].get('feasibility_verdict', ''),
                'new_feas': new_map[c].get('feasibility_verdict', ''),
                'old_score': old_map[c].get('feasibility_score', 0),
                'new_score': new_map[c].get('feasibility_score', 0),
                'old_review': old_map[c].get('review_verdict', ''),
                'new_review': new_map[c].get('review_verdict', ''),
            }
            for c in sorted(common)
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', default='tmp_re15_eval/smoke_20')
    parser.add_argument('--new', default='tmp_re21_eval/smoke_20')
    args = parser.parse_args()

    result = compare(args.old, args.new)
    out_path = Path('tmp_re21_eval/comparison.json')
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                        encoding='utf-8')

    print(f"=== Comparison ({result['n_common']} common cases) ===")
    print(f"Avg accept: {result['old_avg_accept']} → {result['new_avg_accept']}")
    print(f"not_recommended: {result['old_not_recommended']} → {result['new_not_recommended']}")
    print(f"BLOCK: {result['old_block']} → {result['new_block']}")
    print(f"Improved: {result['cases_improved']}, Regressed: {result['cases_regressed']}")
    print(f"\nSaved to: {out_path}")


if __name__ == '__main__':
    main()
