# Re04 Resource Retrieval Eval Report

Source JSONL: `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 5 |
| pass | 3 |
| weak | 2 |
| fail | 0 |
| blocked | 0 |
| pass_rate | 60.0% |
| pass+weak_rate (SOP 合格线 ≥ 80%) | 100.0% |
| 强噪声 case 数 (SOP 上限 ≤ 1) | 0 |

## 每题 (Per-case)

| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | pass | 23 | 3 | 1 | 1 | 2 | N | all_metrics_met |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | pass | 27 | 0 | 6 | 3 | 4 | N | all_metrics_met |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | pass | 42 | 0 | 6 | 5 | 5 | N | all_metrics_met |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 0 | 0 | 5 | 6 | N | dataset+repo=0 < 1 |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | weak | 27 | 3 | 6 | 4 | 1 | N | all_metrics_met |
