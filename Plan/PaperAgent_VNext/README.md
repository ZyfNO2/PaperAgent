# PaperAgent vNext 重构规划入口

> Status: **PLANNING ONLY**  
> Branch: `docs/paperagent-vnext-refactor-plan`  
> Base: `master@dffce680ea8ca02d0a76112f8e5641a14c678e6f`

## 1. 分支性质

本分支只用于 PaperAgent vNext 的架构审计、重构方案、迁移顺序、测试设计和验收标准。

本分支允许修改的内容仅包括：

- `Plan/PaperAgent_VNext/**` 下的 Markdown、表格和规划附件；
- 与重构决策直接相关的架构说明、风险清单、测试矩阵和 Handoff 文档。

本分支禁止修改：

- `apps/**`、`packages/**`、`skills/**` 中的生产代码；
- `tests/**` 或任何现有测试实现；
- `.github/**`、`pyproject.toml`、锁文件、启动脚本和运行配置；
- Prompt、fixture、示例数据、前端、数据库 schema；
- 任何会改变当前 PaperAgent 行为的文件。

因此，本分支的代码树仅作为现状参考。任何实现均应在规划冻结后另开开发分支完成。

## 2. 重构目标

PaperAgent vNext 计划将当前“微节点堆叠 + 多重修复回路 + 大型共享 State”结构收敛为：

```text
宏 Workflow
+ 有界工具子图
+ 单一确定性质量门
+ 最小上下文构建
+ 可审计 Trace / Replay / Eval
```

首要目标：

1. 降低正常路径 LLM 调用次数、总 Token、延迟和成本；
2. 删除测试集特化、固定案例答案、领域硬编码和 Prompt 泄题路径；
3. 保留 LangGraph 对条件路由、Checkpoint 和 Human-in-the-Loop 的真实价值；
4. 建立域外测试、Trace、上下文预算和确定性评估合同；
5. 通过旁路 v2 架构迁移，避免直接破坏现有主线。

## 3. 不变边界

重构后仍需保留 PaperAgent 的项目边界：

- 它是证据工作台和研究规划助手，不是全自动论文生成器；
- `pending / accepted / rejected / failed verification` 等证据状态不能被弱化；
- 未验证资料不能直接支持结论；
- 不运行用户上传代码；
- 不伪造论文、引用、数据集、仓库和实验结果；
- 人工审核和学术判断仍是最终边界。

## 4. 文档索引

- [01 架构与 Workflow 收敛方案](01_Architecture_and_Workflow_Plan.md)
- [02 迁移路线、优先级与验收标准](02_Migration_Roadmap_and_Acceptance.md)
- [03 现有工程与 PaperClaw 借鉴矩阵](03_Reference_Reuse_Matrix.md)
- [04 风险登记与待决策项](04_Risk_Register_and_Open_Decisions.md)

## 5. 后续实施原则

规划冻结后，实施应遵循：

1. 新建独立开发分支，不在本规划分支写代码；
2. 先建立 v2 旁路入口和 feature flag，不原地替换旧图；
3. 首次实现只迁移无修复循环的正常主路径；
4. 所有实现均需有域外测试和调用成本对照；
5. 只有 Shadow Run 达到验收标准后，才讨论默认切换；
6. 旧代码删除必须是最后阶段，且需单独 PR。
