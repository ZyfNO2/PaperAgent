"""Re3.0 batch run script — full-chain redesign verification.

Usage:
    python apps/api/scripts/re30_batch_run.py --cases smoke3
    python apps/api/scripts/re30_batch_run.py --cases batch20
    python apps/api/scripts/re30_batch_run.py --cases all --topics "topic1,topic2"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('FAST_JSON_PRIMARY', 'deepseek')
os.environ.setdefault('PAPERAGENT_SKIP_SEARCH_PLANNER', 'true')

# --- Case definitions ---

# Phase 1-4 smoke test (3 cases)
SMOKE_3 = [
    ("V-YOLO", "基于yolo的农作物识别", "工科AI", "中"),
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究", "三维视觉/SLAM", "中-高"),
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究", "NLP/医学", "高"),
]

# Phase 5.2 progressive cases (5 cases)
PROGRESSIVE_5 = [
    ("ENG-THESIS-022", "基于深度学习的钢铁表面缺陷检测研究", "工业缺陷检测", "中"),
    ("ENG-THESIS-074", "基于深度学习的混凝土桥梁裂缝检测研究", "土木/基础设施", "低-中"),
    ("ENG-THESIS-028", "基于YOLOv5的绝缘子检测与缺陷识别方法研究", "电力/轨交巡检", "中"),
    ("ENG-THESIS-010", "基于深度学习的交通标志检测与识别研究", "自动驾驶", "中"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究", "医学/人体", "高"),
]

# Phase 5.4 full batch (20 cases)
BATCH_20 = [
    ("ENG-THESIS-002", "基于深度学习的磁瓦在线检测技术研究", "工业缺陷检测", "中"),
    ("ENG-THESIS-022", "基于深度学习的钢铁表面缺陷检测研究", "工业缺陷检测", "中"),
    ("ENG-THESIS-010", "基于深度学习的交通标志检测与识别研究", "自动驾驶", "中"),
    ("ENG-THESIS-066", "面向自动驾驶中多模态融合感知算法的攻击和防御", "自动驾驶", "高"),
    ("ENG-THESIS-016", "基于深度学习的视觉SLAM语义地图的研究", "三维视觉/SLAM", "中-高"),
    ("ENG-THESIS-048", "面向动态环境的视觉SLAM研究", "三维视觉/SLAM", "中-高"),
    ("ENG-THESIS-027", "基于YOLOv5模型的遥感影像飞机目标检测", "遥感/无人机", "中"),
    ("ENG-THESIS-038", "基于深度学习的无人机图像目标检测算法研究", "遥感/无人机", "中"),
    ("ENG-THESIS-046", "基于视觉的机械臂的目标检测和避障路径规划研究与应用", "机器人/机械臂", "高"),
    ("ENG-THESIS-063", "基于3D视觉的机械臂无序抓取系统研究", "机器人/机械臂", "高"),
    ("ENG-THESIS-074", "基于深度学习的混凝土桥梁裂缝检测研究", "土木/基础设施", "低-中"),
    ("ENG-THESIS-079", "基于结构光的隧道裂缝检测技术研究与实现", "土木/基础设施", "中-高"),
    ("ENG-THESIS-028", "基于YOLOv5的绝缘子检测与缺陷识别方法研究", "电力/轨交巡检", "中"),
    ("ENG-THESIS-093", "基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究", "电力/轨交巡检", "中"),
    ("ENG-THESIS-092", "海上风机叶片缺陷检测及分类", "能源装备", "中-高"),
    ("ENG-THESIS-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究", "能源装备", "中-高"),
    ("ENG-THESIS-004", "基于改进YOLOv4模型的快速目标检测与测距算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-034", "基于深度学习的目标检测算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究", "医学/人体", "高"),
    ("V-YOLO", "基于yolo的农作物识别", "工科AI", "中"),
]

CASE_SETS = {
    "smoke3": SMOKE_3,
    "progressive5": PROGRESSIVE_5,
    "batch20": BATCH_20,
}


def run_single(case_id, topic, domain, difficulty, out_base):
    t0 = time.time()
    try:
        from apps.api.app.services.agents.graph import research_graph as rg

        state_in = {
            'case_id': case_id, 'topic': topic,
            'user_constraints': {'topic_zh': topic},
            'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
        }
        g = rg.build_graph()
        out = g.invoke(state_in, config={
            'configurable': {'thread_id': case_id},
            'recursion_limit': 100,
        })
        elapsed = round(time.time() - t0, 2)

        out_dir = Path(out_base) / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'state.json').write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        (out_dir / 'trace.json').write_text(
            json.dumps(out.get('trace_events') or [], ensure_ascii=False, indent=2, default=str),
            encoding='utf-8')

        feas = out.get('feasibility_report') or {}
        review = out.get('review_report') or {}
        result = {
            'case_id': case_id, 'topic': topic, 'domain': domain, 'difficulty': difficulty,
            'status': 'done', 'elapsed_s': elapsed,
            'n_papers': len(out.get('verified_papers') or []),
            'n_weak': len(out.get('weak_papers') or []),
            'n_repos': len(out.get('repo_candidates') or []),
            'n_datasets': len(out.get('dataset_candidates') or []),
            'n_nodes': len(out.get('trace_events') or []),
            'n_innovation': len(out.get('innovation_points') or []),
            'feasibility_verdict': feas.get('verdict', ''),
            'feasibility_score': feas.get('score', 0),
            'review_verdict': review.get('overall_verdict', ''),
            'has_final': bool(out.get('final_recommendation')),
        }
        print(f"  DONE {case_id}: {elapsed}s, {result['n_papers']} papers, "
              f"repos={result['n_repos']}, ds={result['n_datasets']}, "
              f"feas={result['feasibility_verdict']}({result['feasibility_score']}), "
              f"review={result['review_verdict']}, inn={result['n_innovation']}")
        return result
    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        err = f"{type(exc).__name__}: {str(exc)[:500]}"
        print(f"  ERROR {case_id}: {err}")
        out_dir = Path(out_base) / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'error.txt').write_text(err, encoding='utf-8')
        return {'case_id': case_id, 'topic': topic, 'domain': domain, 'difficulty': difficulty,
                'status': 'error', 'elapsed_s': elapsed, 'error': err,
                'n_papers': 0, 'has_final': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', default='deepseek')
    parser.add_argument('--cases', default='smoke3', choices=list(CASE_SETS.keys()) + ['all'])
    parser.add_argument('--topics', default='', help='Comma-separated custom topics')
    parser.add_argument('--output-dir', default='')
    args = parser.parse_args()

    os.environ['FAST_JSON_PRIMARY'] = args.provider

    if args.topics:
        cases = [(f"CUSTOM-{i+1}", t.strip(), "custom", "?") for i, t in enumerate(args.topics.split(','))]
    else:
        cases = CASE_SETS[args.cases]

    out_base = args.output_dir or f'tmp_re30_eval/{args.cases}'
    Path(out_base).mkdir(parents=True, exist_ok=True)

    print(f"Re3.0 batch: {len(cases)} cases, provider={args.provider}, set={args.cases}")
    print(f"Output: {Path(out_base).resolve()}")
    print()

    results = []
    consecutive_errors = 0
    batch_start = time.time()

    for i, (cid, topic, domain, difficulty) in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {cid}: {topic}")
        r = run_single(cid, topic, domain, difficulty, out_base)
        results.append(r)

        if r['status'] == 'error':
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("  3 consecutive errors — pausing 60s")
                time.sleep(60)
                r2 = run_single(cid, topic, domain, difficulty, out_base)
                results[-1] = r2
                consecutive_errors = 0 if r2['status'] == 'error' else 0
        else:
            consecutive_errors = 0

        # Incremental summary
        summary = {
            'provider': args.provider, 'case_set': args.cases,
            'n_cases': len(results),
            'n_done': sum(1 for r in results if r['status'] == 'done'),
            'n_has_final': sum(1 for r in results if r.get('has_final')),
            'n_errors': sum(1 for r in results if r['status'] == 'error'),
            'results': results,
        }
        Path(out_base + '/summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    n_done = sum(1 for r in results if r['status'] == 'done')
    n_final = sum(1 for r in results if r.get('has_final'))
    n_err = sum(1 for r in results if r['status'] == 'error')
    elapsed = round(time.time() - batch_start, 0)
    print("\n=== Summary ===")
    print(f"Total: {len(results)}, Done: {n_done}, Has final: {n_final}, Errors: {n_err}")
    print(f"Elapsed: {elapsed}s")
    print(f"Saved to: {Path(out_base).resolve()}")


if __name__ == '__main__':
    main()
