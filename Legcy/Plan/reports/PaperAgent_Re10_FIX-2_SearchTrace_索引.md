# Re10 FIX-2 SearchTrace 索引

> 起草日: 2026-07-04
> 数据来源: Loop A 5 typical + Loop B 10 sample + Iter 1 retest 2

## Loop A 5 typical — `tmp_re04_eval/re10_fix2_typical_cases`

### TYPICAL-01 (Loop A 5 typical)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_typical_cases\traces\TYPICAL-01.json`
- topic: 基于Unet的钢材裂缝分割
- rounds: 3
- final: paper_n=8 baseline_n=0 dataset_n=0 repo_n=1
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=1 acc=1 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=2 acc=2 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-02 (Loop A 5 typical)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_typical_cases\traces\TYPICAL-02.json`
- topic: 基于三维成像的损伤智能检测
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=2
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=1 acc=1 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=1 acc=1 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-03 (Loop A 5 typical)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_typical_cases\traces\TYPICAL-03.json`
- topic: 基于多时相遥感数据的作物早期识别
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=1
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=1 acc=1 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-04 (Loop A 5 typical)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_typical_cases\traces\TYPICAL-04.json`
- topic: 基于大语言模型的医学问答答案可信度评估
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=1
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=1 acc=1 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-05 (Loop A 5 typical)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_typical_cases\traces\TYPICAL-05.json`
- topic: X dynamic scene dataset
- rounds: 3
- final: paper_n=5 baseline_n=0 dataset_n=0 repo_n=1
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=1 acc=1 actions=['openalex=error', 'arxiv=no_results', 'github=success']
  - round 2: new_cand=3 acc=3 actions=['openalex=error', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=2 acc=2 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

## Loop B 10 sample — `tmp_re04_eval/re10_fix2_sample10`

### TYPICAL-01 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-01.json`
- topic: 室内移动机器人目标搜寻与抓取研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=6
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=3 acc=3 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-02 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-02.json`
- topic: 基于点云多平面检测的三维重建关键技术研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=3
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=error']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results/fb=huggingface']

### TYPICAL-03 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-03.json`
- topic: 随机纹理背景下弱小缺陷检测的深度学习方法研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=3
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-04 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-04.json`
- topic: 基于深度学习的视觉SLAM语义地图的研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=4
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=1 acc=1 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-05 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-05.json`
- topic: 基于深度学习的三维点云补全方法研究
- rounds: 3
- final: paper_n=5 baseline_n=0 dataset_n=0 repo_n=3
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=5 acc=5 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-06 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-06.json`
- topic: 基于深度学习的钢铁表面缺陷检测研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=4
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=1 acc=1 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-07 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-07.json`
- topic: 基于改进YOLOv4模型的快速目标检测与测距算法研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=6
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=3 acc=3 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-08 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-08.json`
- topic: 基于多种数据库的改进YOLO算法研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=6
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=3 acc=3 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-09 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-09.json`
- topic: 基于深度学习的新材料地板缺陷检测技术研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=4
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=1 acc=1 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']

### TYPICAL-10 (Loop B 10 sample)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_sample10\traces\TYPICAL-10.json`
- topic: 基于深度卷积神经网络的巡检图像电力部件识别方法研究
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=3
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=3 acc=3 actions=['openalex=error', 'openalex=error', 'github=success']
  - round 2: new_cand=6 acc=6 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

## Iter 1 retest 2 — `tmp_re04_eval/re10_fix2_iter1_retest`

### TYPICAL-01 (Iter 1 retest 2)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_iter1_retest\traces\TYPICAL-01.json`
- topic: 基于多分辨率网络的桥梁裂缝分割算法研究
- rounds: 3
- final: paper_n=7 baseline_n=0 dataset_n=0 repo_n=2
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=0 acc=0 actions=['openalex=error', 'openalex=error', 'github=no_results']
  - round 2: new_cand=8 acc=8 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=1 acc=1 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']

### TYPICAL-02 (Iter 1 retest 2)
- file: `G:\PaperAgent\tmp_re04_eval\re10_fix2_iter1_retest\traces\TYPICAL-02.json`
- topic: 基于视觉的机械臂的目标检测和避障路径规划研究与应用
- rounds: 3
- final: paper_n=6 baseline_n=0 dataset_n=0 repo_n=3
- remaining_gaps: ['dataset_gap', 'baseline_gap']
  - round 1: new_cand=0 acc=0 actions=['openalex=error', 'openalex=error', 'github=no_results']
  - round 2: new_cand=9 acc=9 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=success']
  - round 3: new_cand=0 acc=0 actions=['openalex=success/fb=crossref', 'openalex=success/fb=crossref', 'github=no_results']
