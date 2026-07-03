# PaperAgent Re08 弱项补证明细 (16 cases = 3 fail + 13 weak)

> 起草日：2026-07-03
> 范围：Re08 SOP §4.3 GapRepairPlanner 产物
> 数据来源：`tmp_re04_eval/balanced40_re08/<batch>/<case_id>.json` 的 `repair_plan` 字段

## 0. 一屏总览

| 维度 | 数值 |
|---|---:|
| fail cases (含 repair_plan) | 3 |
| weak cases (含 repair_plan) | 13 |
| 总定向 query 数 | 159 |

---

## ENG-THESIS-043 — `fail`

**Title**: 基于无人机平台的动态目标检测系统开发

**Reason**: quarantined_candidates=2; datasets_present_but_no_topic_dataset; all_evidence_critical_consistency_error; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `UAV aerial imagery X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `UAV aerial imagery dynamic object detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `UAV aerial imagery dynamic object detection YOLOv8 survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `UAV aerial imagery X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv8 UAV aerial imagery`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X UAV aerial imagery dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `UAV aerial imagery X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv8 UAV aerial imagery`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X UAV aerial imagery dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: quarantined_candidates=2; all_evidence_critical_consistency_error

---

## ENG-THESIS-048 — `fail`

**Title**: 面向动态环境的视觉SLAM研究

**Reason**: quarantined_candidates=1; no_dataset_or_data_gap_note; all_evidence_critical_consistency_error; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `dynamic scene dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `dynamic scene X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `dynamic scene visual odometry implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `dynamic scene X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X ORB-SLAM dynamic scene`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X dynamic scene dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `dynamic scene X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X ORB-SLAM dynamic scene`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X dynamic scene dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: quarantined_candidates=1; all_evidence_critical_consistency_error

---

## ENG-THESIS-075 — `fail`

**Title**: 基于深度学习的混凝土路面裂缝检测研究

**Reason**: quarantined_candidates=2; no_dataset_or_data_gap_note; core_n=1_but_no_effective_core; all_evidence_critical_consistency_error; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `concrete pavement dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `concrete pavement X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `concrete pavement crack detection implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `core_n=1_but_no_effective_core`  →  target_role: `core_paper`

- **[arxiv]** `concrete pavement crack detection deep learning survey`
  - *why*: targets core_paper; closes 'core_n=1_but_no_effective_core'
- **[arxiv]** `concrete pavement crack detection benchmark paper`
  - *why*: targets core_paper; closes 'core_n=1_but_no_effective_core'
- **[openalex]** `concrete pavement crack detection state-of-the-art`
  - *why*: targets parallel_paper; closes 'core_n=1_but_no_effective_core'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `concrete pavement X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning concrete pavement`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X concrete pavement dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `concrete pavement X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning concrete pavement`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X concrete pavement dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: quarantined_candidates=2; all_evidence_critical_consistency_error

---

## ENG-THESIS-005 — `weak`

**Title**: 随机纹理背景下弱小缺陷检测的深度学习方法研究

**Reason**: baseline_is_self_cannot_find_degradation; datasets_present_but_no_topic_dataset; object_axis_missing; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `random texture background X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `random texture background small object detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `random texture background small object detection YOLOv8 survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `object_axis_missing`  →  target_role: `baseline`

- **[openalex]** `random texture background small object detection benchmark`
  - *why*: targets baseline; closes 'object_axis_missing'
- **[huggingface]** `random texture background public dataset`
  - *why*: targets dataset; closes 'object_axis_missing'
- **[github]** `random texture background small object detection github implementation`
  - *why*: targets repo; closes 'object_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `random texture background X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv8 random texture background`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X random texture background dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `object_axis_missing`  →  target_role: `baseline`

- **[openalex]** `random texture background small object detection benchmark`
  - *why*: targets baseline; closes 'object_axis_missing'
- **[huggingface]** `random texture background public dataset`
  - *why*: targets dataset; closes 'object_axis_missing'
- **[github]** `random texture background small object detection github implementation`
  - *why*: targets repo; closes 'object_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `random texture background X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv8 random texture background`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X random texture background dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: baseline_is_self_cannot_find_degradation

---

## ENG-THESIS-014 — `weak`

**Title**: 基于生成对抗网络的织物缺陷检测算法研究

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `fabric texture images X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `fabric texture images fabric defect detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `fabric texture images fabric defect detection GAN survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `fabric texture images X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X GAN fabric texture images`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X fabric texture images dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `fabric texture images X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X GAN fabric texture images`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X fabric texture images dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-015 — `weak`

**Title**: 基于患者虚拟定位的三维人体重建关键技术研究

**Reason**: dataset+repo=0 < 1; no_dataset_or_data_gap_note; object_axis_missing; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `X dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `X X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `X X implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `object_axis_missing`  →  target_role: `baseline`

- **[openalex]** `X X benchmark`
  - *why*: targets baseline; closes 'object_axis_missing'
- **[huggingface]** `X public dataset`
  - *why*: targets dataset; closes 'object_axis_missing'
- **[github]** `X X github implementation`
  - *why*: targets repo; closes 'object_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `X X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X X X`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X X dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `object_axis_missing`  →  target_role: `baseline`

- **[openalex]** `X X benchmark`
  - *why*: targets baseline; closes 'object_axis_missing'
- **[huggingface]** `X public dataset`
  - *why*: targets dataset; closes 'object_axis_missing'
- **[github]** `X X github implementation`
  - *why*: targets repo; closes 'object_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `X X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X X X`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X X dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: dataset+repo=0 < 1

---

## ENG-THESIS-028 — `weak`

**Title**: 基于YOLOv5的绝缘子检测与缺陷识别方法研究

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `insulator X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `insulator insulator detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `insulator insulator detection YOLOv5 survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv5 insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLOv5 insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-032 — `weak`

**Title**: 基于深度学习的液晶屏表面缺陷检测方法研究

**Reason**: no_dataset_or_data_gap_note; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `LCD panel dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `LCD panel X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `LCD panel surface defect detection implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `LCD panel X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning LCD panel`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X LCD panel dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `LCD panel X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning LCD panel`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X LCD panel dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-040 — `weak`

**Title**: 基于改进YOLO网络与极限学习机的绝缘子故障检测

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `insulator X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `insulator insulator fault detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `insulator insulator fault detection YOLO survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLO insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLO insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-066 — `weak`

**Title**: 面向自动驾驶中多模态融合感知算法的攻击和防御

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `autonomous vehicle X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `autonomous vehicle object detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `autonomous vehicle object detection multimodal sensor fusion survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `autonomous vehicle X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X multimodal sensor fusion autonomous vehicle`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X autonomous vehicle dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `autonomous vehicle X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X multimodal sensor fusion autonomous vehicle`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X autonomous vehicle dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-073 — `weak`

**Title**: 面向汽车自动驾驶的模拟图像生成技术及应用研究

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `driving scene X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `driving scene simulated image generation real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `driving scene simulated image generation GAN survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `driving scene X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X GAN driving scene`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X driving scene dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `driving scene X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X GAN driving scene`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X driving scene dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-080 — `weak`

**Title**: 基于三维重建裂缝损伤检测算法研究

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `concrete cracks X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `concrete cracks crack detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `concrete cracks crack detection Structure from Motion (SfM) survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `concrete cracks X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X Structure from Motion (SfM) concrete cracks`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X concrete cracks dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `concrete cracks X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X Structure from Motion (SfM) concrete cracks`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X concrete cracks dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-089 — `weak`

**Title**: 基于深度学习和双目立体视觉的道路路面损伤检测研究

**Reason**: dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `road pavement surface dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `road pavement surface X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `road pavement surface pavement distress detection implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `road pavement surface X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning road pavement surface`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X road pavement surface dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `road pavement surface X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X deep learning road pavement surface`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X road pavement surface dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: dataset+repo=0 < 1

---

## ENG-THESIS-091 — `weak`

**Title**: 基于云计算的输电线路缺陷检测平台

**Reason**: dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `transmission lines dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `transmission lines X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `transmission lines transmission line defect detection implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `transmission lines X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X cloud computing transmission lines`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X transmission lines dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `transmission lines X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X cloud computing transmission lines`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X transmission lines dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: dataset+repo=0 < 1

---

## ENG-THESIS-093 — `weak`

**Title**: 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究

**Reason**: datasets_present_but_no_topic_dataset; scenario_axis_missing

### gap: `datasets_present_but_no_topic_dataset`  →  target_role: `dataset`

- **[huggingface]** `catenary insulator X benchmark`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[huggingface]** `catenary insulator surface defect detection real-world dataset`
  - *why*: targets dataset; closes 'datasets_present_but_no_topic_dataset'
- **[openalex]** `catenary insulator surface defect detection YOLO survey`
  - *why*: targets parallel_paper; closes 'datasets_present_but_no_topic_dataset'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `catenary insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLO catenary insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X catenary insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `catenary insulator X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X YOLO catenary insulator`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X catenary insulator dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

---

## ENG-THESIS-096 — `weak`

**Title**: 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究

**Reason**: dataset+repo=0 < 1; no_dataset_or_data_gap_note; scenario_axis_missing

### gap: `no_dataset_or_data_gap_note`  →  target_role: `dataset`

- **[huggingface]** `wind turbine blade dataset benchmark`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[huggingface]** `wind turbine blade X dataset collection`
  - *why*: targets dataset; closes 'no_dataset_or_data_gap_note'
- **[github]** `wind turbine blade wind turbine blade anti-icing implementation github`
  - *why*: targets repo; closes 'no_dataset_or_data_gap_note'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `wind turbine blade X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X graphene film joule heating wind turbine blade`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X wind turbine blade dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

### gap: `scenario_axis_missing`  →  target_role: `parallel_paper`

- **[openalex]** `wind turbine blade X detection`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[openalex]** `X graphene film joule heating wind turbine blade`
  - *why*: targets parallel_paper; closes 'scenario_axis_missing'
- **[huggingface]** `X wind turbine blade dataset`
  - *why*: targets dataset; closes 'scenario_axis_missing'

**Unrepairable**: dataset+repo=0 < 1

