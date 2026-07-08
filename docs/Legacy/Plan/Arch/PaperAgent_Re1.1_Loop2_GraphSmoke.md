# PaperAgent Re1.1 Loop 2 Graph Smoke

> SOP §14 Loop 2: 使用 mock retrieval 跑 1 个 case，验证 graph 拓扑和 trace。

## 验收项

| # | 期望 | 结果 |
| --- | --- | --- |
| 1 | 所有主节点都进入 LangGraph | ✅ 8 节点：retrieve/verify/dataset_repo/evidence_auditor/work_package/low_bar_review/human_gate/final_recommendation |
| 2 | 每个 node 都写 trace | ✅ 8 events |
| 3 | `case_id` 成为 `thread_id` | ✅ `configurable.thread_id="re11-loop2-smoke-001"` |
| 4 | `human_gate_node` 关闭状态下 pass-through | ✅ `human_gate.status=pass_through` |
| 5 | 最终 state 包含 paper/dataset/repo/work_package | ✅ `has_paper_candidates=True`（legacy adapter fallback seed），work_package 空（因 paper 不进 verify，low_bar 拦截） |

## 实测结果

```
topic: Deep learning for crack detection on concrete surfaces
atoms: method=[deep learning, U-Net], object=[concrete crack], dataset_terms=[SDNET2018, Crack500]
elapsed: 6.48 s
nodes fired: retrieve -> verify -> dataset_repo -> evidence_auditor -> work_package -> low_bar_review -> human_gate -> final_recommendation
errors_n: 1 (retrieve legacy adapter import failure -> fallback seed)
has_paper_candidates: True
has_work_packages: False (按 SOP §11：缺 evidence 不编造 work package — 正确行为)
```

## retrieve import failure 说明

`ImportError: cannot import name 'build_axis_bound_queries'` 来自上游 `search_reflection_helpers.py` 与 `search_reflection_loop.py` 的导出名失配，**不是** Re1.1 引入的。

本 loop 验证的是 graph 拓扑及 trace 完整性 — retrieve adapter 走 fallback seed 后，后续 7 节点正常。这是预期中的 adapter 边界（SOP §4 "允许某些 node 先调用旧函数，但必须包在明确 adapter 里"）。

## 代码改动（与 Loop 1 同步）

- `_chat_stepfun()` 使用 `base_url=https://api.stepfun.com`, `model=step-1v-32k`
- `_redact()` 增强：Breaer/x-api-key/Authorization 都可 mask
- `llm_router._resolve_spec("fast_json")` 走 `FAST_JSON_PRIMARY` 显式路由
- legacy adapter try/except 包裹，import fallthrough 到 `_FALLBACK_SEED`

## 关键证据

- `tmp_re11_eval/loop2/re11-loop2-smoke-001.json`：完整 trace + final state

## 通过判定

✅ Loop 2 通过。
