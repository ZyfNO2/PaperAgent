# Re04 Resource Retrieval Eval Report

Source JSONL: `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 5 |
| pass | 4 |
| weak | 1 |
| fail | 0 |
| blocked | 0 |
| pass_rate | 80.0% |
| pass+weak_rate (SOP 合格线 ≥ 80%) | 100.0% |
| 强噪声 case 数 (SOP 上限 ≤ 1) | 0 |

## 每题 (Per-case)

| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | pass | 26 | 0 | 1 | 2 | 10 | N | all_metrics_met |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | weak | 17 | 0 | 4 | 2 | 3 | N | baseline_is_self_cannot_find_degradation |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | pass | 38 | 1 | 2 | 2 | 8 | N | all_metrics_met |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | pass | 11 | 2 | 3 | 4 | 4 | N | all_metrics_met |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | pass | 19 | 0 | 1 | 2 | 3 | N | all_metrics_met |
