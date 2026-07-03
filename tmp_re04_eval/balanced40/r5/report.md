# Re04 Resource Retrieval Eval Report

Source JSONL: `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 5 |
| pass | 4 |
| weak | 0 |
| fail | 1 |
| blocked | 0 |
| pass_rate | 80.0% |
| pass+weak_rate (SOP 合格线 ≥ 80%) | 80.0% |
| 强噪声 case 数 (SOP 上限 ≤ 1) | 1 |

## 每题 (Per-case)

| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | pass | 16 | 0 | 2 | 1 | 5 | N | all_metrics_met |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | pass | 38 | 2 | 6 | 5 | 5 | N | all_metrics_met |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | fail | 22 | 1 | 6 | 6 | 11 | Y | strong_noise_in_core_or_baseline_or_parallel |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | pass | 17 | 0 | 6 | 3 | 3 | N | all_metrics_met |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | pass | 20 | 0 | 3 | 2 | 6 | N | all_metrics_met |
