# PaperAgent Re10 Multi-Loop Reflection 搜索收口 — Balanced40 逐论文审计

> 起草日: 2026-07-03
> 范围: Re10 SOP §11 + §1.4 (Re10 FIX evidence columns)
> 配套: [PaperAgent_Re10_完工报告.md](PaperAgent_Re10_完工报告.md) - 总体报告
**数据汇总**: [PaperAgent_Re10_Balanced40_逐论文审计.csv](PaperAgent_Re10_Balanced40_逐论文审计.csv) (case-level, 40 cases)
**候选论文清单**: [PaperAgent_Re10_Balanced40_候选论文.csv](PaperAgent_Re10_Balanced40_候选论文.csv) (candidate-level)
**Trace 索引**: [PaperAgent_Re10_SearchTrace_索引.md](PaperAgent_Re10_SearchTrace_索引.md)

## 1. 全部 40 case 状态表 (含 evidence 列)

| case_id | re08 | re09 | re10_stop | re10_status | evidence_status | attempt | success | error | missing | new_cand | acc_cand | q_repair | u_repair | llm |
|---|---|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ENG-THESIS-015 | weak | weak | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-016 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-018 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-024 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-027 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-028 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-032 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-033 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-043 | fail | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-046 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-050 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-063 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-066 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-074 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-075 | fail | weak | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-080 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-091 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-092 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-093 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-096 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-002 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-003 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-004 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-005 | weak | weak | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-010 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-014 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-022 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-035 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-040 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-048 | fail | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-051 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-058 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-060 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-064 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-072 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-073 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-079 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-083 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-089 | weak | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ENG-THESIS-100 | pass | fail | **no_new_signal** | **blocked_tooling** | tooling_blocked | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |

**Totals**: attempt=238 success=0 error=238 missing=238 new_cand=0 acc_cand=0 q_repair=0 u_repair=0 llm=0

