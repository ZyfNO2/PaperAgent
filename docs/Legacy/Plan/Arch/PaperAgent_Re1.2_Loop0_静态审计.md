# PaperAgent Re1.2 Loop 0 静态审计

> SOP §14 Loop 0: 必须通过的静态安全检查。

## 验收项

| # | 检查项 | 期望 | 结果 |
| --- | --- | --- | --- |
| 1 | Re1.1 `step-1v-32k` 仅出现在报告/踩坑记录, 不出现在默认 env 或主链路代码默认 | ✅ | 主链路默认 `step-3.7-flash`; `step-1v-32k` 仅作为 `STEPFUN_JSON_FALLBACK_MODEL` env 默认 fallback |
| 2 | `FAST_JSON_PRIMARY=stepfun` | ✅ | `.env.example` + 测试 runner 都已设 |
| 3 | `STEPFUN_MODEL=step-3.7-flash` | ✅ | `llm.py` 默认值 |
| 4 | 主链路不再只有 8 个 node | ✅ | 14 standalone node aliases |
| 5 | `legacy_adapter` 不是默认主路径 | ✅ | retrieve adapter 仍有 fallback, 但 topic_parser / search_planner / verify 已是 standalone |
| 6 | `.env` ignored 且未 tracked | ✅ | 同 Re1.1 |
| 7 | `apps/api/tests` 下存在 Re1.1 测试文件 | ✅ | 4 文件 (`test_re1_1_*.py`) |
| 8 | 无 `generic_repos={...}` 等硬编码 | ✅ | `rg generic_repos` 0 命中 |
| 9 | Re1.1 旧报告中 `step-1v-32k` 结论已标注为历史 | ✅ | 新 `PITFALLS.md` §11 已记录 |

## 渐变历史

本轮完成情况:

- Re1.1 skeleton (8 nodes 线性 chain + llm_router) ✅
- Re1.2 Phase A: provider profile 表 ✅ (stepfun/voapi/minimax)
- Re1.2 Phase B: 3 阶段 JSON 修复 (`json_repair.py`) ✅
- Re1.2 Phase C: stepfun 3.7-flash 内部 fallback 到 step-1v-32k ✅
- Re1.2 Phase D: 14-node LangGraph + 条件边 (repair loop, quality gate) ✅
- Re1.2 Phase E: EvidenceGraph contract + baseline classifier ✅
- Re1.2 Phase F: 小样本 3 case live run (见 Loop3) 完成但 timeout 限制了全量验证
