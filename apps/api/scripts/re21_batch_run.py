"""Re2.1 batch run script — same as re15 but outputs to tmp_re21_eval."""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('FAST_JSON_PRIMARY', 'deepseek')

SMOKE_20 = [
    ("ENG-THESIS-015", "基于患者虚拟定位的三维人体重建关键技术研究"),
    ("ENG-THESIS-016", "基于深度学习的视觉SLAM语义地图的研究"),
    ("ENG-THESIS-018", "基于深度学习的三维点云补全方法研究"),
    ("ENG-THESIS-024", "基于深度学习的无监督三维点云配准算法研究"),
    ("ENG-THESIS-027", "基于YOLOv5模型的遥感影像飞机目标检测"),
    ("ENG-THESIS-028", "基于YOLOv5的绝缘子检测与缺陷识别方法研究"),
    ("ENG-THESIS-032", "基于深度学习的液晶屏表面缺陷检测方法研究"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究"),
    ("ENG-THESIS-043", "基于无人机平台的动态目标检测系统开发"),
    ("ENG-THESIS-046", "基于视觉的机械臂的目标检测和避障路径规划研究与应用"),
    ("ENG-THESIS-050", "基于深度学习的自动驾驶感知算法"),
    ("ENG-THESIS-063", "基于3D视觉的机械臂无序抓取系统研究"),
    ("ENG-THESIS-066", "面向自动驾驶中多模态融合感知算法的攻击和防御"),
    ("ENG-THESIS-074", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("ENG-THESIS-075", "基于深度学习的混凝土路面裂缝检测研究"),
    ("ENG-THESIS-080", "基于三维重建裂缝损伤检测算法研究"),
    ("ENG-THESIS-091", "基于云计算的输电线路缺陷检测平台"),
    ("ENG-THESIS-092", "海上风机叶片缺陷检测及分类"),
    ("ENG-THESIS-093", "基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究"),
    ("ENG-THESIS-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究"),
]

SELECTED_10 = [
    ("ENG-THESIS-046", "基于视觉的机械臂的目标检测和避障路径规划研究与应用"),
    ("ENG-THESIS-063", "基于3D视觉的机械臂无序抓取系统研究"),
    ("ENG-THESIS-066", "面向自动驾驶中多模态融合感知算法的攻击和防御"),
    ("ENG-THESIS-092", "海上风机叶片缺陷检测及分类"),
    ("ENG-THESIS-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究"),
    ("ENG-THESIS-015", "基于患者虚拟定位的三维人体重建关键技术研究"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究"),
    ("ENG-THESIS-004", "基于YOLOv4的目标检测与测距方法研究"),
    ("ENG-THESIS-010", "基于深度学习的交通标志检测与识别方法研究"),
    ("ENG-THESIS-079", "基于结构光的隧道裂缝检测算法研究"),
]

ALL_CASES = {cid: topic for cid, topic in SMOKE_20 + SELECTED_10}


def resolve_cases(cases_arg):
    if cases_arg == "smoke_20":
        return list(SMOKE_20)
    if cases_arg == "selected_10":
        return list(SELECTED_10)
    ids = [c.strip() for c in cases_arg.split(",")]
    result = []
    for cid_short in ids:
        full_id = f"ENG-THESIS-{cid_short}" if not cid_short.startswith("ENG-") else cid_short
        if full_id in ALL_CASES:
            result.append((full_id, ALL_CASES[full_id]))
        else:
            print(f"WARNING: case {full_id} not found, skipping")
    return result


def run_single(case_id, topic, out_base):
    t0 = time.time()
    try:
        from apps.api.app.services.agents.graph import research_graph as rg
        state_in = {
            'case_id': case_id, 'topic': topic,
            'user_constraints': {'topic_zh': topic},
            'trace_events': [], 'provider_profile': 'fast_json', 'errors': [],
        }
        g = rg.build_graph()
        out = g.invoke(state_in, config={'configurable': {'thread_id': case_id}})
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
            'case_id': case_id, 'topic': topic, 'status': 'done', 'elapsed_s': elapsed,
            'n_papers': len(out.get('verified_papers') or []),
            'n_weak': len(out.get('weak_papers') or []),
            'n_nodes': len(out.get('trace_events') or []),
            'n_packages': len(out.get('work_packages') or []),
            'n_innovation': len(out.get('innovation_points') or []),
            'feasibility_verdict': feas.get('verdict', ''),
            'feasibility_score': feas.get('score', 0),
            'review_verdict': review.get('overall_verdict', ''),
            'has_final': bool(out.get('final_recommendation')),
        }
        print(f"  DONE {case_id}: {elapsed}s, {result['n_papers']} papers, "
              f"feas={result['feasibility_verdict']}({result['feasibility_score']}), "
              f"review={result['review_verdict']}, inn={result['n_innovation']}")
        return result
    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        err = f"{type(exc).__name__}: {str(exc)[:300]}"
        print(f"  ERROR {case_id}: {err}")
        out_dir = Path(out_base) / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'error.txt').write_text(err, encoding='utf-8')
        return {'case_id': case_id, 'topic': topic, 'status': 'error',
                'elapsed_s': elapsed, 'error': err, 'n_papers': 0, 'has_final': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', default='deepseek')
    parser.add_argument('--cases', default='smoke_20')
    parser.add_argument('--output-dir', default='tmp_re21_eval')
    args = parser.parse_args()

    os.environ['FAST_JSON_PRIMARY'] = args.provider
    cases = resolve_cases(args.cases)
    out_base = args.output_dir
    Path(out_base).mkdir(parents=True, exist_ok=True)

    print(f"Re2.1 batch: {len(cases)} cases, provider={args.provider}")
    print(f"Output: {Path(out_base).resolve()}")
    print()

    results = []
    consecutive_errors = 0
    for i, (cid, topic) in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {cid}: {topic}")
        r = run_single(cid, topic, out_base)
        results.append(r)
        if r['status'] == 'error':
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("  3 consecutive errors — stopping")
                break
        else:
            consecutive_errors = 0

    n_done = sum(1 for r in results if r['status'] == 'done')
    n_final = sum(1 for r in results if r.get('has_final'))
    summary = {'provider': args.provider, 'n_cases': len(results), 'n_done': n_done,
               'n_has_final': n_final, 'results': results}
    sp = Path(out_base) / f'summary_{args.provider}.json'
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f"\n=== Summary ===")
    print(f"Total: {len(results)}, Done: {n_done}, Has final: {n_final}")
    print(f"Saved to: {sp}")


if __name__ == '__main__':
    main()
