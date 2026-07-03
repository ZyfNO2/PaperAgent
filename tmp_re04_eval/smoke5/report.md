# Re04 Resource Retrieval Eval Report

Source JSONL: `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`

## 整体统计 (Aggregate)

| 指标 | 数值 |
|---|---:|
| 总题数 | 5 |
| pass | 0 |
| weak | 1 |
| fail | 4 |
| blocked | 0 |
| pass_rate | 0.0% |
| pass+weak_rate (SOP 合格线 ≥ 80%) | 20.0% |
| 强噪声 case 数 (SOP 上限 ≤ 1) | 0 |

## 每题 (Per-case)

| id | title | status | paper | dataset | repo | baseline | parallel | noise | reason |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | weak | 18 | 0 | 0 | 3 | 4 | N | dataset+repo=0 < 1 |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | fail | 15 | 0 | 6 | 0 | 0 | N | baseline_n=0 < 1 |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | fail | 0 | 0 | 0 | 0 | 0 | N | paper_n=0 < 8; baseline_n=0 < 1; dataset+repo=0 < 1 |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | fail | 0 | 0 | 0 | 0 | 0 | N | paper_n=0 < 8; baseline_n=0 < 1; dataset+repo=0 < 1 |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | fail | 16 | 0 | 0 | 0 | 0 | N | baseline_n=0 < 1; dataset+repo=0 < 1 |
