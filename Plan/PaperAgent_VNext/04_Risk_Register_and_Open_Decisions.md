# PaperAgent vNext 风险登记与待决策项

> Document type: Risk Register  
> Implementation status: **NOT STARTED**

## 1. 风险分级

- `BLOCKER`：不解决不能进入实现或上线；
- `HIGH`：可能导致错误结论、回归或重新形成屎山；
- `MEDIUM`：影响维护性、成本或调试；
- `LOW`：非阻塞优化项。

## 2. 风险登记

| ID | 级别 | 风险 | 触发条件 | 影响 | 规划中的控制措施 |
|---|---|---|---|---|---|
| R-01 | BLOCKER | 测试集答案或固定案例实体进入生产 Prompt | Prompt、fallback 或 fixture 共用 | 域外问题输出旧案例答案 | Prompt/fixture 目录隔离；泄漏扫描；OOD 测试 |
| R-02 | BLOCKER | 未验证 Evidence 直接支持结论 | 状态映射弱化 pending/rejected/failed | 伪造或错误学术结论 | 保留证据状态；Gate 校验证据绑定 |
| R-03 | HIGH | 将多个节点合并后丢失可观测性 | 单次 Workflow 只记录最终文本 | 无法解释耗时、来源和失败 | 结构化 Artifact + span Trace，不保存原始 CoT |
| R-04 | HIGH | v2 继续读取 legacy 大型 ResearchState | 为兼容省事直接复用 | 状态耦合和字段漂移延续 | 新 State + adapter；Workflow 最小上下文 |
| R-05 | HIGH | 单一 Workflow 输出过大导致 schema 失败 | 合并范围过度 | 重试成本上升 | 按同一上下文和原子失败边界合并；限制字段数量 |
| R-06 | HIGH | 单一 Gate 演变成新的万能节点 | 所有逻辑塞入 Gate | 难测试、难维护 | Gate 只校验和路由；业务修复留在对应 Workflow |
| R-07 | HIGH | Shadow Run 使用不同检索结果，比较失真 | legacy/v2 外部环境不一致 | 无法判断架构差异 | 固定输入、预算、Provider；保存 source snapshot |
| R-08 | HIGH | Mock 测试被当成真实 E2E | 只跑 Fake provider | 上线能力被高估 | 明确 offline/real-provider/real-E2E 标签 |
| R-09 | MEDIUM | Context 压缩丢失 required constraints | 只按相似度裁剪 | 输出违反用户条件 | required constraint 不可淘汰；压缩后完整性检查 |
| R-10 | MEDIUM | Evidence ID 在压缩或迁移中变化 | 重新生成随机 ID | 引用无法回放 | 稳定 ID 和 provenance；adapter 显式映射 |
| R-11 | MEDIUM | Recorded Replay 被误解为真实重跑 | 回放不执行模型/工具 | 验收陈述失真 | 报告中区分 recorded replay 与 live E2E |
| R-12 | MEDIUM | v2 fallback 到 legacy 后掩盖失败 | 自动静默回退 | v2 指标虚高 | fallback 必须显式 Trace；统计 fallback rate |
| R-13 | MEDIUM | 多 Provider 行为差异导致 Prompt 漂移 | JSON mode/工具调用能力不同 | schema 和质量不稳定 | Provider contract；模型能力矩阵；Prompt 版本化 |
| R-14 | MEDIUM | Checkpointer 与外部副作用边界不清 | 节点中途下载/写入 | resume 重复执行 | 副作用节点独立；幂等键；safe resume decision |
| R-15 | LOW | 文档规划过度细化但迟迟不实现 | 持续扩展 P2 | 计划膨胀 | P0/P1/P2 边界；每阶段最小 Gate |

## 3. 停止条件

出现以下情况时应停止当前实现阶段并回到规划：

- v2 必须依赖大部分 legacy State 才能运行；
- 正常路径仍需要十次以上 LLM 调用；
- 为通过现有案例再次加入领域关键词分支；
- 无法构造至少六个域外案例；
- Evidence 状态在 adapter 中发生语义丢失；
- repair loop 无法证明有界；
- Trace 无法区分真实调用、fallback、reuse 和 replay；
- 成本或延迟没有可测量基线；
- 实现范围被 Multi-Agent、UI 或外部平台集成占据。

## 4. 待决策项

### D-01：宏 Workflow 的最终拆分数量

候选：

- 4 个核心 LLM Workflow：planning / evidence / method / report；
- 将 evidence 与 method 合并为 3 个；
- 将 method 与 report 拆分 reviewer，形成 5 个。

建议：先以 4 个为默认，通过真实 Token 和 schema 失败率再调整。

### D-02：检索子图是否保留现有 orchestrator

需要在 Phase 0 确认：

- adapter 是否与固定案例耦合；
- 输出 schema 是否稳定；
- 验证状态是否完整；
- 是否可脱离 legacy State 调用。

默认决策：保留工具实现，重写输入输出 adapter。

### D-03：Checkpointer 首选 SQLite 还是 Postgres

规划阶段默认：

- 本地、单实例和面试演示：SQLite；
- 多实例生产：Postgres 候选；
- 不在 v2 主路径跑通前引入多后端抽象。

### D-04：是否第一阶段接入 LangSmith

建议：否。

先建立自有最小 Trace contract，LangSmith 作为可选 exporter/adapter，而不是核心状态来源。

### D-05：语义质量是否使用 LLM Reviewer

建议：按需。

- 确定性规则先执行；
- 只有语义问题无法判断时调用 reviewer；
- reviewer 结果不能覆盖硬约束；
- reviewer 调用计入成本和 Trace。

### D-06：legacy 回退窗口

应在 Shadow Run 后根据：

- v2 fallback rate；
- BLOCKED rate；
- 线上错误；
- checkpoint 迁移情况；
- 用户验收反馈

确定，不在规划阶段写死日期。

## 5. 规划冻结条件

以下文档完成并经过人工审阅后，才能创建首个代码开发分支：

- 节点现状清单；
- Prompt/fixture 泄漏审计；
- legacy 性能和成本基线；
- OOD 测试题与预期判定标准；
- v2 Artifact schema 草案；
- v2 TraceEvent schema 草案；
- 统一 Gate reason_code 清单；
- 兼容 adapter 输入输出合同；
- 实施 PR 拆分和回滚顺序。

## 6. 本分支完成判定

本规划分支的完成不代表 vNext 已实现。它只能标记为：

```text
PLANNING COMPLETE / IMPLEMENTATION NOT STARTED
```

完成条件：

- 分支相对 `master` 的所有变更均为规划文档；
- 不包含源码、测试、配置、Prompt 或 fixture 变更；
- 架构、迁移、复用和风险文档相互一致；
- 后续实现分支边界明确；
- 所有未验证能力均标记为 proposed 或 not started。
