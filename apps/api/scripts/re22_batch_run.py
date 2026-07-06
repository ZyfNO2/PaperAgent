"""Re2.2 100-paper full regression batch run script.

Usage:
    python apps/api/scripts/re22_batch_run.py --provider deepseek --cases all_100
"""
import argparse, json, os, sys, time, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('FAST_JSON_PRIMARY', 'deepseek')

# All 100 cases parsed from docs/PaperAgent_工科学位论文爬取测试集_100篇.md
ALL_100 = [
    ("ENG-THESIS-001", "室内移动机器人目标搜寻与抓取研究", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-002", "基于深度学习的磁瓦在线检测技术研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-003", "基于点云多平面检测的三维重建关键技术研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-004", "基于改进YOLOv4模型的快速目标检测与测距算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-005", "随机纹理背景下弱小缺陷检测的深度学习方法研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-006", "三维重建中点云数据处理关键技术研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-007", "基于视觉的无人机识别与跟踪技术研究", "遥感/无人机目标检测", "中"),
    ("ENG-THESIS-008", "焊点缺陷检测方法研究及其应用", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-009", "点云的三维重建与纹理映射", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-010", "基于深度学习的交通标志检测与识别研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-011", "基于深度学习的磁片表面缺陷检测技术研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-012", "基于深度学习的单图像三维点云重建研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-013", "基于机器视觉的板类堆叠零件分拣系统研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-014", "基于生成对抗网络的织物缺陷检测算法研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-015", "基于患者虚拟定位的三维人体重建关键技术研究", "医学/人体三维视觉", "高"),
    ("ENG-THESIS-016", "基于深度学习的视觉SLAM语义地图的研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-017", "基于深度学习的卫浴陶瓷缺陷检测", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-018", "基于深度学习的三维点云补全方法研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-019", "基于光学图像YOLO算法的废钢识别分类与统计", "工业缺陷检测/机器视觉", "低-中"),
    ("ENG-THESIS-020", "基于深度学习的工件缺陷检测系统研究与设计", "工业缺陷检测/机器视觉", "低-中"),
    ("ENG-THESIS-021", "基于深度学习的自动驾驶感知算法研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-022", "基于深度学习的钢铁表面缺陷检测研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-023", "基于深度学习的新材料地板缺陷检测技术研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-024", "基于深度学习的无监督三维点云配准算法研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-025", "基于激光点云图像融合的三维重建方法与应用", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-026", "基于深度卷积神经网络的巡检图像电力部件识别方法研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-027", "基于YOLOv5模型的遥感影像飞机目标检测", "遥感/无人机目标检测", "中"),
    ("ENG-THESIS-028", "基于YOLOv5的绝缘子检测与缺陷识别方法研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-029", "基于多种数据库的改进YOLO算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-030", "基于改进YOLOv5的轻量化违禁物检测技术研究与实践", "工业缺陷检测/机器视觉", "低-中"),
    ("ENG-THESIS-031", "基于YOLO的图像目标检测算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-032", "基于深度学习的液晶屏表面缺陷检测方法研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究", "医学/人体三维视觉", "高"),
    ("ENG-THESIS-034", "基于深度学习的目标检测算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-035", "基于深度学习的带钢表面缺陷检测方法", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-036", "基于YOLOv5的实时检测算法研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-037", "基于YOLO算法的遥感图像飞机目标检测技术研究", "遥感/无人机目标检测", "中"),
    ("ENG-THESIS-038", "基于深度学习的无人机图像目标检测算法研究", "遥感/无人机目标检测", "中"),
    ("ENG-THESIS-039", "基于生成对抗网络的金属表面缺陷视觉检测方法研究", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-040", "基于改进YOLO网络与极限学习机的绝缘子故障检测", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-041", "基于深度学习的废钢定级系统的设计与实现", "工业缺陷检测/机器视觉", "中"),
    ("ENG-THESIS-042", "基于YOLOv3的车牌识别研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-043", "基于无人机平台的动态目标检测系统开发", "遥感/无人机目标检测", "中"),
    ("ENG-THESIS-044", "基于YOLOv5的无人机巡检图像绝缘子检测技术的研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-045", "人群中危险动作综合分析研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-046", "基于视觉的机械臂的目标检测和避障路径规划研究与应用", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-047", "基于深度学习无人驾驶交通安全标志检测与识别研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-048", "面向动态环境的视觉SLAM研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-049", "基于特征点的目标位姿估计与机械臂抓取控制", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-050", "基于深度学习的自动驾驶感知算法", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-051", "基于深度学习的语义SLAM研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-052", "基于深度强化学习的无人驾驶感知与决策研究", "自动驾驶/交通感知", "高"),
    ("ENG-THESIS-053", "复杂动态场景下视觉SLAM研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-054", "基于无模型自适应预测控制的机械臂视觉伺服控制研究", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-055", "基于深度学习的自动驾驶目标检测算法研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-056", "基于深度学习的室内场景语义SLAM研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-057", "基于深度相机的机械臂动态避障规划研究", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-058", "基于深度学习的激光点云环境感知", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-059", "基于全卷积神经网络的视觉SLAM特征提取方法研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-060", "基于深度学习的车道线检测方法研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-061", "交通场景下基于深度学习的目标检测和图像分割研究", "工科AI/计算机视觉", "中"),
    ("ENG-THESIS-062", "面向嵌入式系统应用SLAM算法的研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-063", "基于3D视觉的机械臂无序抓取系统研究", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-064", "面向复杂道路场景的车辆目标检测算法研究与实现", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-065", "基于深度相机的视觉SLAM与路径规划", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-066", "面向自动驾驶中多模态融合感知算法的攻击和防御", "自动驾驶/交通感知", "高"),
    ("ENG-THESIS-067", "基于深度学习的车辆检测及应用研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-068", "室内动态环境下的语义视觉SLAM方法研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-069", "重载工业机械臂数据逻辑攻击及检测研究", "机器人/机械臂实验系统", "高"),
    ("ENG-THESIS-070", "面向自动驾驶汽车的多线激光雷达动态障碍物检测研究", "自动驾驶/交通感知", "高"),
    ("ENG-THESIS-071", "基于深度学习的国内交通标志检测及分类", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-072", "基于深度学习的动态SLAM研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-073", "面向汽车自动驾驶的模拟图像生成技术及应用研究", "自动驾驶/交通感知", "中"),
    ("ENG-THESIS-074", "基于深度学习的混凝土桥梁裂缝检测研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-075", "基于深度学习的混凝土路面裂缝检测研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-076", "基于深度学习的道路裂缝检测研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-077", "基于深度学习的路面裂缝检测研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-078", "面向多尺度特征融合的混凝土路面裂缝检测算法研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-079", "基于结构光的隧道裂缝检测技术研究与实现", "土木/交通基础设施损伤检测", "中-高"),
    ("ENG-THESIS-080", "基于三维重建裂缝损伤检测算法研究", "三维视觉/SLAM/点云", "中-高"),
    ("ENG-THESIS-081", "基于深度学习的混凝土细观损伤特征检测研究", "土木/交通基础设施损伤检测", "中-高"),
    ("ENG-THESIS-082", "基于深度学习的道路异常状态检测方法研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-083", "基于多分辨率网络的桥梁裂缝分割算法研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-084", "基于U-Net卷积网络的地质岩层裂缝检测方法", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-085", "高速公路沥青面裂缝检测识别算法的研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-086", "基于深度学习的轨道板裂缝检测技术研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-087", "在建地铁隧道衬砌渗漏水检测方法的改进与应用", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-088", "基于深度学习的路面多特征检测系统的研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-089", "基于深度学习和双目立体视觉的道路路面损伤检测研究", "土木/交通基础设施损伤检测", "中-高"),
    ("ENG-THESIS-090", "基于计算机视觉的道路裂纹检测研究", "土木/交通基础设施损伤检测", "低-中"),
    ("ENG-THESIS-091", "基于云计算的输电线路缺陷检测平台", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-092", "海上风机叶片缺陷检测及分类", "能源装备/故障诊断", "中-高"),
    ("ENG-THESIS-093", "基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-094", "基于SCADA数据的风机叶片结冰诊断研究", "能源装备/故障诊断", "中-高"),
    ("ENG-THESIS-095", "基于深度学习的输电杆塔关键点检测方法研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究", "能源装备/故障诊断", "中-高"),
    ("ENG-THESIS-097", "基于计算机视觉的电力设备识别与热异常检测方法研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-098", "基于深度学习的接触网绝缘子识别及其污秽检测技术研究", "电力/轨交巡检视觉", "中"),
    ("ENG-THESIS-099", "基于电动云台的风机叶片表面图像跟踪拍摄", "能源装备/故障诊断", "中-高"),
    ("ENG-THESIS-100", "基于深度学习的配电设备视觉识别技术研究", "电力/轨交巡检视觉", "中"),
]


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
            'case_id': case_id, 'topic': topic, 'domain': domain, 'difficulty': difficulty,
            'status': 'done', 'elapsed_s': elapsed,
            'n_papers': len(out.get('verified_papers') or []),
            'n_weak': len(out.get('weak_papers') or []),
            'n_nodes': len(out.get('trace_events') or []),
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
        return {'case_id': case_id, 'topic': topic, 'domain': domain, 'difficulty': difficulty,
                'status': 'error', 'elapsed_s': elapsed, 'error': err,
                'n_papers': 0, 'has_final': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', default='deepseek')
    parser.add_argument('--cases', default='all_100')
    parser.add_argument('--output-dir', default='tmp_re22_eval/all_100')
    args = parser.parse_args()

    os.environ['FAST_JSON_PRIMARY'] = args.provider
    out_base = args.output_dir
    Path(out_base).mkdir(parents=True, exist_ok=True)
    progress_log = Path('tmp_re22_eval/progress.log')
    progress_log.parent.mkdir(parents=True, exist_ok=True)

    cases = ALL_100
    print(f"Re2.2 batch: {len(cases)} cases, provider={args.provider}")
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
                # Retry once
                r2 = run_single(cid, topic, domain, difficulty, out_base)
                results[-1] = r2
                if r2['status'] == 'error':
                    consecutive_errors = 0  # Reset, skip this case
                else:
                    consecutive_errors = 0
        else:
            consecutive_errors = 0

        # Progress log every 10 cases
        if i % 10 == 0:
            n_done = sum(1 for r in results if r['status'] == 'done')
            n_err = sum(1 for r in results if r['status'] == 'error')
            elapsed = round(time.time() - batch_start, 0)
            avg = round(elapsed / i, 1)
            line = f"[{i}/{len(cases)}] {n_done} done, {n_err} failed, avg={avg}s, elapsed={elapsed}s"
            with open(progress_log, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
            print(f"  PROGRESS: {line}")

        # Append to summary incrementally
        summary = {'provider': args.provider, 'n_cases': len(results),
                    'n_done': sum(1 for r in results if r['status'] == 'done'),
                    'n_has_final': sum(1 for r in results if r.get('has_final')),
                    'results': results}
        Path(out_base + '/summary_deepseek.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    n_done = sum(1 for r in results if r['status'] == 'done')
    n_final = sum(1 for r in results if r.get('has_final'))
    summary = {'provider': args.provider, 'n_cases': len(results), 'n_done': n_done,
               'n_has_final': n_final, 'results': results}
    sp = Path(out_base) / 'summary_deepseek.json'
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f"\n=== Summary ===")
    print(f"Total: {len(results)}, Done: {n_done}, Has final: {n_final}")
    print(f"Saved to: {sp}")


if __name__ == '__main__':
    main()
