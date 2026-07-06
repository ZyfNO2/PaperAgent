"""Re2.1 3-case verification script.

Runs V-MED / V-SLAM / V-CRACK and outputs results to tmp_re21_eval/verify/.
"""
import os, sys, json, time
from pathlib import Path

os.environ['FAST_JSON_PRIMARY'] = 'deepseek'
sys.path.insert(0, r'G:\PaperAgent')

from apps.api.app.services.agents.graph import research_graph as rg

V_CASES = [
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究"),
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究"),
    ("V-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
]


def run_graph(vid, topic):
    state_in = {
        'case_id': vid, 'topic': topic,
        'user_constraints': {'topic_zh': topic},
        'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
    }
    g = rg.build_graph()
    return g.invoke(state_in, config={'configurable': {'thread_id': vid}})


def run_verification(label=""):
    results = {}
    for vid, topic in V_CASES:
        t0 = time.time()
        try:
            out = run_graph(vid, topic)
            elapsed = round(time.time() - t0, 2)
            traces = out.get('trace_events') or []

            # Check retrieve tools
            retrieve_tools = []
            for t in traces:
                if t.get('node') in ('retrieve', 'paper_retriever'):
                    for tc in t.get('tool_calls', []):
                        tool = tc.get('tool', '')
                        if tool:
                            retrieve_tools.append(tool)

            results[vid] = {
                'has_final': bool(out.get('final_recommendation')),
                'elapsed_s': elapsed,
                'n_verified': len(out.get('verified_papers') or []),
                'n_weak': len(out.get('weak_papers') or []),
                'n_candidates': len(out.get('paper_candidates') or []),
                'feasibility_verdict': (out.get('feasibility_report') or {}).get('verdict', ''),
                'feasibility_score': (out.get('feasibility_report') or {}).get('score', 0),
                'review_verdict': (out.get('review_report') or {}).get('overall_verdict', ''),
                'n_innovation': len(out.get('innovation_points') or []),
                'n_work_packages': len(out.get('work_packages') or []),
                'n_baseline': len(out.get('baseline_candidates') or []),
                'n_parallel': len(out.get('parallel_candidates') or []),
                'retrieve_tools': retrieve_tools,
                'crash': False,
            }

            # Save state
            out_dir = Path('tmp_re21_eval') / vid
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / 'state.json').write_text(
                json.dumps(out, ensure_ascii=False, indent=2, default=str),
                encoding='utf-8')
            (out_dir / 'trace.json').write_text(
                json.dumps(traces, ensure_ascii=False, indent=2, default=str),
                encoding='utf-8')

            fv = results[vid]['feasibility_verdict']
            fs = results[vid]['feasibility_score']
            rv = results[vid]['review_verdict']
            nv = results[vid]['n_verified']
            print(f'{vid}: {elapsed}s, {nv} verified, feas={fv}({fs}), review={rv}, '
                  f'tools={retrieve_tools}')

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            results[vid] = {'crash': True, 'error': str(e)[:300], 'elapsed_s': elapsed}
            print(f'{vid}: CRASH ({elapsed}s): {str(e)[:100]}')

    # Save verification result
    verify_dir = Path('tmp_re21_eval/verify')
    verify_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    label_str = f"_{label}" if label else ""
    out_path = verify_dir / f'verify_{ts}{label_str}.json'
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str),
                        encoding='utf-8')
    print(f'\nVerification saved to: {out_path}')
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='', help='Label for this verification run')
    args = parser.parse_args()
    run_verification(args.label)
