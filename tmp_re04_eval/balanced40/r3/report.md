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
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | pass | 14 | 0 | 1 | 3 | 3 | N | all_metrics_met |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | weak | 22 | 0 | 4 | 3 | 1 | N | all_metrics_met |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | pass | 23 | 3 | 6 | 2 | 2 | N | all_metrics_met |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | weak | 194 | 4 | 6 | 1 | 0 | N | baseline_is_self_cannot_find_degradation |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | pass | 18 | 0 | 4 | 3 | 3 | N | all_metrics_met |
