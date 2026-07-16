# PaperAgent

PaperAgent 正在以 `v0.1` 从零重建。

当前 `v0.1` 分支只包含新架构的设计与开发合同；旧 PaperAgent 源码、测试、配置、Prompt 和兼容逻辑不迁移到新工作树。

## 当前状态

```text
Version: v0.1
Stage: design and test-contract freeze
Implementation: not started
Development method: mandatory TDD
```

## v0.1 目标

从零建立一个最小、可运行、可测试的 LangGraph 研究工作流骨架，包括：

- 新的 State contract；
- 新的顶层 StateGraph；
- 有界 Retrieval subgraph；
- 结构化 Node contract；
- 单一确定性 Quality Gate；
- Human-in-the-Loop interrupt/resume；
- 最小 Trace 和 Checkpoint；
- 固定 Fake LLM / Fake Search 测试合同；
- 域外测试与测试集泄漏检查。

## 强制开发规则

1. 所有生产代码必须由失败测试驱动；
2. 每个工作包遵循 `RED → GREEN → REFACTOR`；
3. LLM 节点先使用固定模拟回复通过测试，再接真实 Provider；
4. 测试不得依赖 Prompt 文本包含特定关键词来选择回复；
5. Fake Provider 必须按 `task + scenario + call_index` 返回版本化 fixture；
6. 真实模型测试不能替代确定性离线测试；
7. 未通过验收矩阵，不允许将 `v0.1` 合并回 `master`。

## v0.1 开发文档

按以下顺序阅读和执行：

1. [执行案](docs/v0.1/EXECUTION_PLAN.md)
2. [图与节点设计](docs/v0.1/GRAPH_AND_NODES.md)
3. [State 与 Schema 合同](docs/v0.1/STATE_CONTRACTS.md)
4. [TDD 策略](docs/v0.1/TDD_STRATEGY.md)
5. [LLM 模拟输入输出与测试 Fixtures](docs/v0.1/LLM_TEST_FIXTURES.md)
6. [开发顺序与提交规范](docs/v0.1/DEVELOPMENT_WORKFLOW.md)
7. [v0.1 验收标准](docs/v0.1/ACCEPTANCE.md)

这些文档共同构成 v0.1 的开发合同。代码实现与文档冲突时，应先更新并审阅文档，再修改代码。

## v0.1 之后

- [v0.2 至 v1.0 后续版本路线图](docs/ROADMAP_AFTER_V0.1.md)
- [v0.2 文献检索与 Web-First 上线方案](docs/planning/V0.2_LITERATURE_RETRIEVAL.md)

后续版本继续使用强制 TDD，并按“单版本单主目标”的方式推进。v0.1 未完成验收前，不提前实现后续版本功能。

## 分支

- `master`：重置后的新主线；
- `v0.1`：v0.1 设计和实现分支；
- `backup/legacy-pre-v0.1-20260716`：旧 PaperAgent 完整备份，只读参考；
- `docs/paperagent-vnext-refactor-plan`：早期重构规划过程文档。

旧实现只用于阅读和借鉴。新代码不得导入旧节点、旧 State、旧 Prompt、旧 fixture 或兼容层。
