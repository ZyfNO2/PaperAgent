# Re04 Resource Retrieval Eval Report

Source JSONL: `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 5 |
| pass | 5 |
| weak | 0 |
| fail | 0 |
| blocked | 0 |
| pass_rate | 100.0% |
| pass+weak_rate (SOP 合格线 ≥ 80%) | 100.0% |
| 强噪声 case 数 (SOP 上限 ≤ 1) | 0 |

## 每题 (Per-case)

| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | pass | 19 | 2 | 3 | 3 | 7 | N | all_metrics_met |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | pass | 19 | 2 | 5 | 3 | 2 | N | all_metrics_met |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | pass | 30 | 0 | 6 | 3 | 6 | N | all_metrics_met |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | pass | 24 | 1 | 6 | 2 | 5 | N | all_metrics_met |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | pass | 19 | 0 | 6 | 3 | 3 | N | all_metrics_met |
