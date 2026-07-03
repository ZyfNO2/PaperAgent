# PaperAgent Re10 Multi-Loop Reflection 搜索收口 — Balanced40 逐论文审计

> 起草日: 2026-07-03
> 范围: Re10 SOP §11
> 配套: [PaperAgent_Re10_完工报告.md](PaperAgent_Re10_完工报告.md) - 总体报告
**数据汇总**: [PaperAgent_Re10_Balanced40_逐论文审计.csv](PaperAgent_Re10_Balanced40_逐论文审计.csv) (case-level, 40 cases)
**候选论文清单**: [PaperAgent_Re10_Balanced40_候选论文.csv](PaperAgent_Re10_Balanced40_候选论文.csv) (candidate-level)
**Trace 索引**: [PaperAgent_Re10_SearchTrace_索引.md](PaperAgent_Re10_SearchTrace_索引.md)

## 1. 全部 40 case 状态表

| case_id | re08 | re09 | re10_stop | re10_rounds | seed_n | elapsed_s |
|---|---|---|:---:|:---:|---:|---:|
| ENG-THESIS-015 | weak | weak | **no_new_signal** | 2 | 29 | 71.82 |
| ENG-THESIS-016 | pass | fail | **no_new_signal** | 2 | 28 | 108.44 |
| ENG-THESIS-018 | pass | fail | **no_new_signal** | 2 | 39 | 74.47 |
| ENG-THESIS-024 | pass | fail | **no_new_signal** | 2 | 24 | 84.19 |
| ENG-THESIS-027 | pass | fail | **no_new_signal** | 2 | 26 | 82.17 |
| ENG-THESIS-028 | weak | fail | **no_new_signal** | 2 | 30 | 79.69 |
| ENG-THESIS-032 | weak | fail | **no_new_signal** | 2 | 22 | 72.1 |
| ENG-THESIS-033 | pass | fail | **no_new_signal** | 2 | 30 | 92.26 |
| ENG-THESIS-043 | fail | fail | **no_new_signal** | 2 | 24 | 89.07 |
| ENG-THESIS-046 | pass | fail | **no_new_signal** | 2 | 36 | 73.35 |
| ENG-THESIS-050 | pass | fail | **no_new_signal** | 2 | 24 | 70.85 |
| ENG-THESIS-063 | pass | fail | **no_new_signal** | 2 | 63 | 62.16 |
| ENG-THESIS-066 | weak | fail | **no_new_signal** | 2 | 42 | 73.95 |
| ENG-THESIS-074 | pass | fail | **no_new_signal** | 2 | 31 | 90.76 |
| ENG-THESIS-075 | fail | weak | **no_new_signal** | 2 | 36 | 83.07 |
| ENG-THESIS-080 | weak | fail | **no_new_signal** | 2 | 31 | 73.92 |
| ENG-THESIS-091 | weak | fail | **no_new_signal** | 2 | 26 | 83.94 |
| ENG-THESIS-092 | pass | fail | **no_new_signal** | 2 | 26 | 44.2 |
| ENG-THESIS-093 | weak | fail | **no_new_signal** | 2 | 26 | 85.59 |
| ENG-THESIS-096 | weak | fail | **no_new_signal** | 2 | 28 | 79.18 |
| ENG-THESIS-002 | pass | fail | **no_new_signal** | 2 | 18 | 63.51 |
| ENG-THESIS-003 | pass | fail | **no_new_signal** | 2 | 21 | 63.56 |
| ENG-THESIS-004 | pass | fail | **no_new_signal** | 2 | 32 | 82.25 |
| ENG-THESIS-005 | weak | weak | **no_new_signal** | 2 | 217 | 68.62 |
| ENG-THESIS-010 | pass | fail | **no_new_signal** | 2 | 22 | 83.39 |
| ENG-THESIS-014 | weak | fail | **no_new_signal** | 2 | 30 | 76.9 |
| ENG-THESIS-022 | pass | fail | **no_new_signal** | 2 | 38 | 80.55 |
| ENG-THESIS-035 | pass | fail | **no_new_signal** | 2 | 27 | 70.63 |
| ENG-THESIS-040 | weak | fail | **no_new_signal** | 2 | 24 | 90.25 |
| ENG-THESIS-048 | fail | fail | **no_new_signal** | 2 | 32 | 79.03 |
| ENG-THESIS-051 | pass | fail | **no_new_signal** | 2 | 18 | 63.05 |
| ENG-THESIS-058 | pass | fail | **no_new_signal** | 2 | 46 | 93.38 |
| ENG-THESIS-060 | pass | fail | **no_new_signal** | 2 | 29 | 72.19 |
| ENG-THESIS-064 | pass | fail | **no_new_signal** | 2 | 23 | 81.13 |
| ENG-THESIS-072 | pass | fail | **no_new_signal** | 2 | 23 | 79.27 |
| ENG-THESIS-073 | weak | fail | **no_new_signal** | 2 | 35 | 84.7 |
| ENG-THESIS-079 | pass | fail | **no_new_signal** | 2 | 33 | 76.85 |
| ENG-THESIS-083 | pass | fail | **no_new_signal** | 2 | 48 | 100.84 |
| ENG-THESIS-089 | weak | fail | **no_new_signal** | 2 | 25 | 86.45 |
| ENG-THESIS-100 | pass | fail | **no_new_signal** | 2 | 36 | 88.67 |

