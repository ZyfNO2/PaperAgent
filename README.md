# PaperAgent

PaperAgent 正在以 `v0.1` 从零重建。

当前主线只保留新架构的设计文档；旧 PaperAgent 源码、测试、配置和历史实现不迁移到新工作树。

## 当前状态

```text
Version: v0.1
Stage: architecture and node design
Implementation: not started
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
- 域外测试与泄漏检查。

## 文档

- [v0.1 执行案](docs/v0.1/EXECUTION_PLAN.md)
- [v0.1 图与节点设计](docs/v0.1/GRAPH_AND_NODES.md)

## 分支

- `master`：重置后的新主线；
- `v0.1`：v0.1 实现分支；
- `backup/legacy-pre-v0.1-20260716`：旧 PaperAgent 完整备份，只读参考；
- `docs/paperagent-vnext-refactor-plan`：重构规划过程文档。

旧实现只用于阅读和借鉴。新代码不得导入旧节点、旧 State、旧 Prompt、旧 fixture 或兼容层。
