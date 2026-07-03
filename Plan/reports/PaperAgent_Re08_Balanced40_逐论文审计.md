# Re07 Resource Retrieval Eval Report

Source JSONL: `tmp_re04_eval\balanced40 (Re05 LLM-online raw dumps, Re08 re-audit)`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 40 |
| pass | 24 |
| weak | 13 |
| fail | 3 |
| blocked | 0 |
| pass_rate | 60.0% |
| pass+weak_rate (Re07 合格线 ≥ 90%) | 92.5% |
| quarantined_total (Re07 §3.5) | 3 |
| axis_not_evaluable cases (Re07 §3.2) | 0 |

## 每题 (Per-case)

| id | title | status | paper | eff_baseline | eff_parallel | eff_core | topic_ds | quarantined | axis | reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | weak | 17 | 2 | 3 | 1 | 0 | 0 | evaluable | dataset+repo=0 < 1; no_dataset_or_data_gap_note; object_axis_missing; scenario_a |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | pass | 22 | 4 | 6 | 6 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | pass | 34 | 1 | 7 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | weak | 22 | 4 | 2 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | weak | 15 | 3 | 1 | 0 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | pass | 27 | 5 | 9 | 7 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | fail | 16 | 3 | 2 | 3 | 0 | 2 | evaluable | quarantined_candidates=2; datasets_present_but_no_topic_dataset; all_evidence_cr |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | pass | 22 | 3 | 8 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | pass | 57 | 7 | 6 | 11 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | weak | 28 | 4 | 2 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | pass | 19 | 3 | 7 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | pass | 19 | 3 | 2 | 5 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | pass | 30 | 3 | 6 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | pass | 24 | 2 | 5 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | fail | 19 | 2 | 3 | 0 | 0 | 2 | evaluable | quarantined_candidates=2; no_dataset_or_data_gap_note; core_n=1_but_no_effective |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | weak | 17 | 4 | 4 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 4 | 2 | 2 | 0 | 0 | evaluable | dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | pass | 17 | 2 | 7 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | weak | 15 | 4 | 4 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 1 | 3 | 1 | 0 | 0 | evaluable | dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | pass | 17 | 2 | 4 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | pass | 19 | 5 | 1 | 7 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | pass | 23 | 2 | 2 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | weak | 200 | 1 | 0 | 0 | 0 | 0 | evaluable | baseline_is_self_cannot_find_degradation; datasets_present_but_no_topic_dataset; |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | pass | 18 | 3 | 3 | 2 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | weak | 20 | 4 | 5 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | pass | 28 | 3 | 5 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | pass | 25 | 5 | 9 | 7 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | weak | 14 | 2 | 3 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | fail | 20 | 2 | 3 | 1 | 0 | 1 | evaluable | quarantined_candidates=1; no_dataset_or_data_gap_note; all_evidence_critical_con |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | pass | 16 | 1 | 5 | 4 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | pass | 38 | 5 | 5 | 12 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | pass | 22 | 6 | 11 | 8 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | pass | 17 | 3 | 3 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | pass | 20 | 2 | 6 | 7 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | weak | 23 | 1 | 2 | 0 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | pass | 27 | 3 | 4 | 1 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | pass | 42 | 5 | 5 | 2 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 5 | 6 | 0 | 0 | 0 | evaluable | dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | pass | 27 | 4 | 1 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; scenario_axis_missing |
