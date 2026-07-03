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
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | pass | 20 | 2 | 0 | 4 | 5 | N | all_metrics_met |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | pass | 28 | 4 | 6 | 3 | 5 | N | all_metrics_met |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | pass | 25 | 1 | 1 | 5 | 9 | N | all_metrics_met |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | pass | 14 | 2 | 0 | 2 | 3 | N | all_metrics_met |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | fail | 20 | 0 | 6 | 3 | 3 | Y | strong_noise_in_core_or_baseline_or_parallel |
