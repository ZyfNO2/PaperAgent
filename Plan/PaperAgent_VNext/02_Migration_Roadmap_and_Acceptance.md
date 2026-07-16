# PaperAgent vNext 迁移路线、优先级与验收标准

> Document type: Delivery Plan  
> Implementation status: **NOT STARTED**

## 1. 总体策略

采用“冻结旧基线 → v2 旁路 → 正常路径 → 单一修复环 → Trace/Eval → Shadow Run → 默认切换 → 删除旧代码”的顺序。

禁止直接在旧 LangGraph 主图上继续堆叠 vNext 逻辑。

## 2. Phase 0：现状冻结与审计

### 目标

得到可比较的 legacy 基线，并明确每个旧节点的去留。

### 文档产物

- 节点清单：输入、输出、LLM/工具调用、分支、循环、状态字段；
- Prompt 清单和版本来源；
- 领域硬编码与测试特化风险清单；
- 正常路径、修复路径和失败路径时序图；
- 3 个现有案例 + 至少 6 个域外案例的基线数据；
- 节点决策表：`KEEP / MERGE / REWRITE / DELETE`。

### 基线指标

- LLM 调用次数；
- 工具调用次数；
- 输入/输出 Token；
- 估算费用；
- P50/P95 延迟；
- repair 次数；
- schema 失败率；
- Evidence 引用覆盖率；
- 最终任务成功率；
- 域外实体泄漏情况。

### Gate

未完成现状审计，不进入实现阶段。

## 3. Phase 1：v2 旁路骨架

### 目标

建立独立的 v2 目录、状态合同和引擎选择机制，但暂不迁移复杂业务。

### 计划目录

```text
apps/api/app/services/agents_v2/
  graph.py
  state.py
  context_builder.py
  workflows/
  retrieval/
  gates/
  prompts/
  telemetry/
  adapters/
```

### 约束

- 在独立开发分支实现；
- 不修改 legacy 节点内部逻辑；
- 默认仍为 legacy；
- v2 输出必须带 schema_version；
- 所有 Prompt 必须带 prompt_version；
- 不引入 Multi-Agent。

### Gate

- v2 最小空图可构建；
- feature flag 可选择 legacy/v2；
- legacy 回归无变化；
- v2 State 不依赖 legacy ResearchState。

## 4. Phase 2：无循环正常主路径

### 目标

完成四个宏 Workflow 和一次检索子图，先建立可结束的线性主路径。

### 实施顺序

1. `intake_policy`；
2. `research_planning_workflow`；
3. `retrieval_subgraph` 最小版；
4. `evidence_synthesis_workflow`；
5. `method_design_workflow`；
6. `report_workflow`。

### 暂不实现

- 自动 repair；
- 复杂 reflection；
- Gate pass reuse；
- Multi-Agent；
- 长期记忆；
- 完整 UI；
- LLM-as-Judge。

### Gate

- 代表案例均能完成；
- 正常路径核心 LLM 调用不超过 5 次；
- 所有输出通过 schema validation；
- 无测试 fixture 进入生产上下文；
- 无域外实体污染。

## 5. Phase 3：单一质量门与有界修复

### 目标

只增加一个统一 Gate 和最多 1—2 次修复，不恢复旧系统的多 Gate 结构。

### 修复类型

- `REPAIR_RETRIEVAL`：缺少必要证据；
- `REPAIR_EVIDENCE`：证据分类或冲突处理不完整；
- `REPAIR_METHOD`：方法接口、假设或实验计划不完整；
- `HUMAN_REVIEW`：需要用户确认；
- `BLOCKED`：预算、权限、证据或安全边界阻止继续。

### Gate

- 每次修复有 reason_code；
- repair 目标唯一；
- 总修复次数有硬上限；
- 达到上限后显式 BLOCKED，不伪装成功；
- 修复前后 Artifact 可对比；
- 不使用完整 State fingerprint 驱动业务语义。

## 6. Phase 4：Context、Trace、Replay 与 Eval

### ContextBuilder MVP

构建顺序：

```text
collect
→ validate
→ scope
→ deduplicate
→ conflict check
→ estimate token
→ select
→ compact
→ render
```

不可压缩或丢弃：

- 系统安全边界；
- 用户 required constraints；
- Evidence ID 和 source reference；
- 当前 repair reason；
- 人工审核决定。

### Trace MVP

每个 Workflow/工具节点至少记录：

- run/span/parent ID；
- stage 和状态；
- prompt/model/schema 版本；
- input hash；
- evidence refs；
- route decision；
- Token、延迟、费用；
- retry、error 和 fallback；
- payload 脱敏状态。

### Replay MVP

只做 recorded replay：

- 不重新调用模型；
- 不重新执行工具；
- 复现已记录路由和状态转换；
- 检查 Trace 是否自洽。

### Deterministic Eval MVP

- schema success；
- terminal status；
- replay faithful；
- tool failure rate；
- retry count；
- reflection/repair count；
- wall duration；
- token/cost；
- evidence binding；
- leakage detection。

### Gate

Trace 不完整或 Replay 不一致时，不允许宣布 v2 已可上线。

## 7. Phase 5：Shadow Run

### 方法

对相同输入同时运行 legacy 和 v2，但只向用户返回当前默认引擎结果。

### 对比维度

- 任务完成度；
- Evidence 精确性与覆盖率；
- 结论可追溯性；
- 域外泛化；
- Token、费用、延迟；
- 工具失败和 repair；
- 人工审核需求；
- 错误恢复能力。

### Gate

建议达到以下条件后才切换默认：

| 指标 | 目标 |
|---|---:|
| 正常路径核心 LLM 调用 | ≤ 5 |
| 正常路径 LangGraph 宏节点 | ≤ 9 |
| 结构化输出成功率 | ≥ 95% |
| Trace 完整率 | 100% |
| 旧案例专有实体泄漏 | 0 |
| 域外任务成功率 | 不低于 legacy |
| P50 延迟 | 比 legacy 降低 ≥ 40% |
| 单次成功任务 Token | 比 legacy 降低 ≥ 40% |
| 无证据确定性事实 | 0 |
| Repair 类型 | 1 个统一合同 |

指标必须来自实际运行，不得只用 Mock 结果证明。

## 8. Phase 6：默认切换

### 要求

- 通过 feature flag 将 v2 设为默认；
- legacy 保留可回退窗口；
- 明确回退条件和操作文档；
- 监控错误率、成本、延迟和 BLOCKED 比例；
- 不在同一提交中删除 legacy。

## 9. Phase 7：旧代码删除

单独分支和 PR 完成：

- 删除旧节点别名；
- 删除 Re1—Re8 仅用于兼容的状态字段；
- 删除多套 Gate 和分散的 round/cycle/reuse 状态；
- 删除测试集特化 fallback；
- 删除旧 Prompt 和无使用方 normalize 代码；
- 更新文档和迁移说明。

### 删除 Gate

- v2 已稳定运行一个约定观察周期；
- 无业务调用 legacy；
- legacy 数据和 checkpoint 已有迁移或归档策略；
- rollback 方案已验证。

## 10. 优先级

### P0

- 文档冻结；
- 现状审计；
- 域外测试设计；
- v2 状态与宏 Workflow 合同；
- Prompt/fixture 隔离；
- 单一确定性 Gate；
- 最小 Token/Latency/Cost Trace。

### P1

- ContextBuilder；
- SQLite Checkpointer；
- pause/resume；
- recorded replay；
- Shadow Run；
- 引擎切换和回退。

### P2

- LangSmith 接入；
- RAGAS；
- LLM-as-Judge；
- 长期向量记忆；
- 完整 Trace UI；
- Multi-Agent；
- 自动 Prompt 优化。

## 11. 实施分支建议

本规划分支不实施代码。规划通过后建议依次创建：

```text
feat/paperagent-vnext-foundation
feat/paperagent-vnext-mainline
feat/paperagent-vnext-quality-gate
feat/paperagent-vnext-observability
chore/paperagent-vnext-default-switch
chore/paperagent-legacy-removal
```

每个分支只负责一个可验证阶段，避免再次形成跨阶段大提交。
