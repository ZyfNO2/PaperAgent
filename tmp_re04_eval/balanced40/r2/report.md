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
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | pass | 17 | 1 | 6 | 4 | 4 | N | all_metrics_met |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 0 | 0 | 4 | 2 | N | dataset+repo=0 < 1 |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | pass | 17 | 3 | 6 | 2 | 7 | N | all_metrics_met |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | pass | 15 | 3 | 1 | 4 | 4 | N | all_metrics_met |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 0 | 0 | 1 | 3 | N | dataset+repo=0 < 1 |
