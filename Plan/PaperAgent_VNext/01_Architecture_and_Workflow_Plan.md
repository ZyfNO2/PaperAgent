# PaperAgent vNext 架构与 Workflow 收敛方案

> Document type: Architecture Plan  
> Implementation status: **NOT STARTED**

## 1. 问题定义

当前 PaperAgent 的主要复杂度来自长期增量叠加：

- 业务阶段被拆成大量微型 LLM 节点；
- 多个 Gate、repair loop、reflection loop 分别维护轮次和路由；
- 共享 State 同时承载业务产物、控制状态、兼容字段和 telemetry；
- Prompt、fallback、fixture 和生产逻辑之间存在潜在耦合；
- 正常任务也会经过多个 reviewer，导致延迟和成本不可控。

vNext 不以增加功能为目标，而以收敛控制流、隔离职责和提高域外泛化为目标。

## 2. 节点划分规则

### 2.1 合并为单次 LLM Workflow

连续步骤满足以下条件时，应合并为一次结构化调用：

- 中间没有条件分支；
- 没有必须单独提交的外部副作用；
- 使用基本相同的上下文；
- 中间产物不会被其他节点独立消费；
- 失败时可以整体重试；
- 可以通过一个 Pydantic 输出合同完整表达。

### 2.2 保留独立节点

以下职责必须独立：

- 搜索、下载、解析、验证等工具调用；
- 决定下一条边的确定性 Gate；
- Human-in-the-Loop 暂停点；
- Checkpoint / resume 边界；
- 具有独立限流、超时、重试和幂等要求的副作用；
- 必须并发执行的任务。

### 2.3 不保存原始 CoT

Workflow 采用“单次结构化推理、多字段输出”，不要求模型输出完整思维链。

Trace 只保存：

- 输入摘要与 hash；
- Evidence ID；
- 结构化决策和路由原因；
- schema 校验结果；
- 模型、Prompt 版本、Token、延迟和成本；
- 错误和重试信息。

## 3. 目标主图

```text
START
  ↓
intake_policy                         # 确定性
  ↓
research_planning_workflow            # 1 次 LLM
  ↓
retrieval_subgraph                    # 有界工具循环
  ↓
evidence_synthesis_workflow           # 1 次 LLM
  ↓
method_design_workflow                # 1 次 LLM
  ↓
deterministic_quality_gate
  ├─ PASS → report_workflow           # 1 次 LLM
  ├─ REPAIR_RETRIEVAL → retrieval_subgraph
  ├─ REPAIR_METHOD → method_design_workflow
  ├─ HUMAN_REVIEW → human_gate
  └─ BLOCKED → report_workflow
  ↓
human_gate（按配置启用）
  ↓
END
```

正常路径目标：4 次核心 LLM 调用；工具调用数量由检索预算独立约束。

## 4. 宏 Workflow 合同

### 4.1 `research_planning_workflow`

合并候选：

- topic parsing；
- method family exploration；
- evidence gap definition；
- search lane planning；
- query generation。

输出 `ResearchPlanArtifact`：

```text
schema_version
prompt_version
topic_scope
problem_statement
method_families[]
evidence_gaps[]
search_lanes[]
queries[]
known_risks[]
```

约束：不得写死领域实体；不得直接声明论文、数据集或仓库真实存在。

### 4.2 `retrieval_subgraph`

职责：

- 执行搜索计划；
- 解析和验证论文、数据集、仓库、网页和用户材料；
- 将所有结果绑定 `gap_id` 和 `source_id`；
- 保留 `pending / accepted / rejected / failed verification` 状态；
- 输出结构化 Evidence Bundle。

该子图可以包含条件边和有限循环，但禁止由领域关键词选择固定答案。

### 4.3 `evidence_synthesis_workflow`

合并候选：

- dataset/repository semantic extraction；
- evidence graph semantic grouping；
- baseline role classification；
- feasibility analysis。

输出 `EvidenceSynthesisArtifact`：

```text
verified_evidence_refs[]
baseline_candidates[]
resource_assessment
gap_status[]
conflicts[]
feasibility_verdict
feasibility_rationale
```

存在性、URL、DOI、仓库可访问性等事实由工具层确定，LLM 不承担验证职责。

### 4.4 `method_design_workflow`

合并候选：

- work package generation；
- academic method tailoring；
- innovation proposal；
- falsifiable hypothesis；
- experiment and ablation planning。

输出 `MethodProposalArtifact`：

```text
baseline
modules[]
integration_contracts[]
problem_method_insight
falsifiable_hypothesis
minimum_key_experiment
ablation_matrix[]
risks[]
stop_conditions[]
```

模块组合必须作为待验证假设，不得将“A+B+C”本身表述为创新。

### 4.5 `report_workflow`

职责：将已验证 Artifact 编排为最终研究建议，不新增事实。

输出应明确区分：

- verified；
- inferred；
- proposed；
- unknown；
- blocked。

## 5. 单一质量门

vNext 只保留一个统一 Gate 合同：

```json
{
  "verdict": "PASS | REPAIR | HUMAN_REVIEW | BLOCKED",
  "repair_stage": "retrieval | evidence | method | report | null",
  "reason_codes": [],
  "missing_evidence_ids": [],
  "invalid_claim_ids": [],
  "budget_status": {}
}
```

Gate 优先使用确定性校验：

- schema 完整性；
- Evidence ID 是否存在；
- claim 是否绑定证据；
- accepted/rejected 状态是否合法；
- 引用覆盖率；
- 冲突是否显式处理；
- 预算和循环上限；
- 是否出现测试集或其他案例专有实体泄漏。

仅在确定性检查无法判断语义质量时，才调用独立 reviewer；reviewer 不在正常路径默认执行。

## 6. State 分层

目标状态分为四类：

```text
RunContext
ResearchArtifacts
ExecutionState
TelemetryState
```

### RunContext

- run_id / thread_id；
- user request；
- constraints；
- run mode；
- network policy；
- budgets。

### ResearchArtifacts

- research_plan；
- evidence_bundle；
- evidence_synthesis；
- method_proposal；
- final_report。

### ExecutionState

- current_stage；
- status；
- retry_count；
- repair_target；
- pending_human_action。

### TelemetryState

- trace references；
- usage；
- warnings；
- errors。

禁止 Workflow 直接读取整个全局状态。每个 Workflow 由 ContextBuilder 生成最小输入。

## 7. Prompt 与输出治理

统一链路：

```text
Prompt Template
→ LLM Response
→ JSON Decode
→ Pydantic Validation
→ Semantic Validation
→ Normalized Artifact
```

禁止：

- 每个节点自行定义不一致的解析和 fallback；
- 静默丢弃未知字段；
- 生产 Prompt 引用 golden answer；
- Prompt loader 访问测试 fixture；
- 通过 topic 名称、候选数量或固定 ID 判断测试案例；
- 无证据时补充固定论文、数据集或 baseline。

## 8. 兼容策略

vNext 采用旁路实现：

```text
PAPERAGENT_ENGINE=legacy
PAPERAGENT_ENGINE=v2
```

初期要求：

- 外部 API 尽量不变；
- legacy 与 v2 Artifact 通过 adapter 转换；
- v2 不复用 legacy 的大型 ResearchState；
- v2 不继承旧节点别名；
- v2 失败时可以显式回退 legacy，但回退事件必须进入 Trace；
- 未通过 Shadow Run 前，不修改默认引擎。
