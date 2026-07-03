# Re06 Resource Retrieval Eval Report

Source JSONL: `tmp_re04_eval\balanced40 (Re05 LLM-online raw dumps, Re06 re-audit)`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 40 |
| pass | 0 |
| weak | 37 |
| fail | 3 |
| blocked | 0 |
| pass_rate | 0.0% |
| pass+weak_rate (SOP 合格线 ≥ 90%) | 92.5% |
| critical_consistency_error cases (SOP §6.1 = 0) | 3 |
| core=0 但 status=pass (SOP §6.3 = 0) | 0 |

## 每题 (Per-case)

| id | title | status | paper | topic_ds | pretrain_ds | repo | baseline(d/p) | parallel(d/p) | consistency_err | reason |
|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | weak | 17 | 0 | 0 | 0 | 0/2 | 0/3 | 0 | dataset+repo=0 < 1; no_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | weak | 22 | 0 | 0 | 6 | 0/4 | 0/6 | 0 | no_dataset; core_n=6_but_no_direct_core |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | weak | 34 | 0 | 3 | 2 | 0/1 | 0/7 | 0 | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | weak | 22 | 0 | 1 | 0 | 0/4 | 0/2 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | weak | 15 | 0 | 0 | 1 | 0/3 | 0/1 | 0 | no_dataset |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | weak | 27 | 0 | 2 | 1 | 0/5 | 0/9 | 0 | datasets_present_but_no_topic_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | fail | 16 | 0 | 2 | 0 | 0/3 | 0/3 | 2 | critical_consistency_error_n=2; datasets_present_but_no_topic_dataset; core_n=4_ |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | weak | 22 | 0 | 2 | 0 | 0/3 | 0/8 | 0 | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | weak | 57 | 0 | 0 | 6 | 0/7 | 0/6 | 0 | no_dataset; core_n=11_but_no_direct_core |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | weak | 28 | 0 | 2 | 6 | 0/4 | 0/2 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | weak | 19 | 0 | 2 | 3 | 0/3 | 0/7 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | weak | 19 | 0 | 2 | 5 | 0/3 | 0/2 | 0 | datasets_present_but_no_topic_dataset; core_n=5_but_no_direct_core |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | weak | 30 | 0 | 0 | 6 | 0/3 | 0/6 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | weak | 24 | 0 | 1 | 6 | 0/2 | 0/5 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | fail | 19 | 0 | 0 | 6 | 0/3 | 0/3 | 2 | critical_consistency_error_n=2; no_dataset; core_n=1_but_no_direct_core; metadat |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | weak | 17 | 0 | 1 | 6 | 0/4 | 0/4 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 0 | 0 | 0 | 0/4 | 0/2 | 0 | dataset+repo=0 < 1; no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | weak | 17 | 0 | 3 | 6 | 0/2 | 0/7 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | weak | 15 | 0 | 3 | 1 | 0/4 | 0/4 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 0 | 0 | 0 | 0/1 | 0/3 | 0 | dataset+repo=0 < 1; no_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | weak | 17 | 0 | 0 | 1 | 0/2 | 0/4 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | weak | 19 | 0 | 2 | 0 | 0/5 | 0/1 | 0 | datasets_present_but_no_topic_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | weak | 23 | 0 | 3 | 6 | 0/2 | 0/2 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | weak | 200 | 0 | 3 | 6 | 0/1 | 0/0 | 0 | baseline_is_self_cannot_find_degradation; datasets_present_but_no_topic_dataset |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | weak | 18 | 0 | 0 | 4 | 0/3 | 0/3 | 0 | no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | weak | 20 | 0 | 2 | 0 | 0/4 | 0/5 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | weak | 28 | 0 | 4 | 6 | 0/3 | 0/5 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | weak | 25 | 0 | 1 | 1 | 0/5 | 0/9 | 0 | datasets_present_but_no_topic_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | weak | 14 | 0 | 2 | 0 | 0/2 | 0/3 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | fail | 20 | 0 | 0 | 6 | 0/3 | 0/3 | 1 | critical_consistency_error_n=1; no_dataset; core_n=1_but_no_direct_core; metadat |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | weak | 16 | 0 | 0 | 2 | 0/1 | 0/5 | 0 | no_dataset; core_n=4_but_no_direct_core |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | weak | 38 | 0 | 2 | 6 | 0/5 | 0/5 | 0 | datasets_present_but_no_topic_dataset; core_n=12_but_no_direct_core |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | weak | 22 | 0 | 1 | 6 | 0/6 | 0/11 | 0 | datasets_present_but_no_topic_dataset; core_n=8_but_no_direct_core |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | weak | 17 | 0 | 0 | 6 | 0/3 | 0/3 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | weak | 20 | 0 | 0 | 3 | 0/2 | 0/6 | 0 | no_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | weak | 23 | 0 | 3 | 1 | 0/1 | 0/2 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | weak | 27 | 0 | 0 | 6 | 0/3 | 0/4 | 0 | no_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | weak | 42 | 0 | 0 | 6 | 0/5 | 0/5 | 0 | no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 0 | 0 | 0 | 0/5 | 0/6 | 0 | dataset+repo=0 < 1; no_dataset |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | weak | 27 | 0 | 3 | 6 | 0/4 | 0/1 | 0 | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |
