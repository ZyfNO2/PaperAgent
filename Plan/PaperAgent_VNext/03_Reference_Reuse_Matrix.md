# PaperAgent vNext 现有工程与 PaperClaw 借鉴矩阵

> Document type: Reference Matrix  
> Policy: **REFERENCE ONLY — NO IMPLEMENTATION IN THIS BRANCH**

## 1. 借鉴原则

本规划允许研究 PaperAgent 和 PaperClaw 的已实现能力，但不在本分支复制、移动或修改代码。

后续实现时采用以下原则：

- 复用经过验证的合同和失败边界，优先于复制整套实现；
- 只引入 vNext 当前阶段需要的最小能力；
- 不为“架构完整”提前引入 Multi-Agent、外部 exporter 或复杂 UI；
- 所有借鉴都必须重新适配 PaperAgent 的证据工作台语义；
- PaperAgent 的 evidence status、人工审核和不运行用户代码边界保持优先。

## 2. PaperAgent 现有能力处理矩阵

| 能力 | 当前价值 | vNext 决策 | 说明 |
|---|---|---|---|
| 多源检索适配器 | 高 | KEEP / ADAPT | 工具层可保留，统一输出 Evidence contract |
| PDF / 网页 / 图片材料解析 | 高 | KEEP / ADAPT | 只保留真实解析和来源追踪，不与固定案例绑定 |
| Evidence 工作台状态 | 核心 | KEEP | 保留 pending/accepted/rejected/failed verification 语义 |
| URL / DOI / 仓库验证 | 高 | KEEP | 必须保持确定性工具职责，不交给 LLM 猜测 |
| FinalPackage / 报告产物 | 中高 | ADAPT | 改为消费 v2 Artifacts，不读取大型 legacy State |
| ReportQuality | 中 | REVIEW | 可拆成确定性规则，语义 reviewer 按需触发 |
| Human Gate | 高 | KEEP | 作为真实暂停点，不作为普通 pass-through 节点 |
| LangGraph Checkpointer | 高 | REBUILD CONTRACT | 采用 v2 thread/run contract，不继承旧 State |
| 旧微型 LLM 节点 | 低 | MERGE / DELETE | 合并为宏 Workflow |
| 多套 Reflection Gate | 低 | DELETE / REPLACE | 收敛为统一 Gate |
| Gate fingerprint/reuse/cycle | 局部价值 | DO NOT PORT DIRECTLY | 先通过简化控制流消除重入问题 |
| 旧兼容 alias | 低 | DELETE LATE | 只在最终 legacy removal 阶段处理 |
| 固定案例 fallback | 风险 | REMOVE | 不得进入 v2 |

## 3. PaperClaw 可借鉴能力

| PaperClaw 能力 | 借鉴内容 | PaperAgent vNext 使用阶段 | 不直接照搬的部分 |
|---|---|---|---|
| Context contracts | scope、priority、required constraint、source refs | Phase 4 | Coding Agent 专用角色和工具上下文 |
| ContextBuilder | collect→validate→scope→dedup→conflict→estimate→select→compact→render | Phase 4 | 全量复杂策略和未进入 Gate 的增强候选 |
| Context compaction | required constraint 和 evidence ref 保留 | Phase 4 | 针对代码文件 diff 的压缩策略 |
| Session / SQLite | run、conversation、checkpoint 持久化边界 | Phase 4 | PaperClaw 特有 session command 和 TUI 行为 |
| Safe resume | 未知副作用不自动重放 | Phase 4 | Coding 工具 mutation 分类的具体实现 |
| Versioned TraceEvent | schema version、run/span、事件投影 | Phase 4 | 与 PaperAgent 无关的 Worker/Team 字段 |
| Trace redaction | Secret、路径、payload 脱敏 | Phase 4 | 无关的 shell/code payload 规则 |
| Atomic JSONL/SQLite | 可恢复和可审计写入 | Phase 4 | 外部 trace push 暂缓 |
| Read-only Inspector | timeline、aggregate、error chain | Phase 4/P1 | TUI 面板暂缓 |
| Recorded Replay | 不执行模型或工具的控制流回放 | Phase 4 | Guarded live replay 暂缓 |
| Deterministic Trace Eval | completed、tool failure、retry、duration、reflection 等指标 | Phase 4 | MultiAgent Global Verify 暂缓 |
| Provider reliability | timeout、bounded retry、normalized metadata | Phase 2/P1 | PaperClaw provider adapter 的完整代码结构 |
| MultiAgent | 面试展示价值 | P2 | 当前 vNext 不实现 |

## 4. 不应直接迁移的 PaperClaw 能力

当前阶段明确暂缓：

- MultiAgent Coordinator、Worker 和团队面板；
- Global Verify；
- Guarded live replay；
- 外部 HTTPS Trace exporter；
- 完整 Textual TUI；
- Coding Agent 专用 tool mutation replay；
- 与用户代码执行相关的工作区能力。

原因：这些能力不解决 PaperAgent 当前的主要问题，提前迁移会重新引入过度工程。

## 5. Academic Method Tailoring 的使用边界

`academic-method-tailoring` 适合作为：

- baseline 选择和证据审计方法；
- 模块兼容性检查模板；
- 可证伪假设和实验矩阵设计模板；
- 方法提案的 reviewer 合同。

不适合作为：

- 直接自动拼接模块并宣称创新的执行器；
- 自动运行用户仓库或实验代码的 Agent；
- 在证据不足时补全论文、结果或引用的 fallback；
- 绕过 PaperAgent accepted/verified 状态的直接结论生成器。

vNext 中建议将其方法论约束融入 `method_design_workflow` 的 schema 和质量门，而不是整体嵌入为一个自治 Agent。

## 6. 复用决策记录格式

后续每项借鉴必须记录：

```text
Reference source
→ Borrowed contract
→ PaperAgent-specific adaptation
→ Rejected parts
→ Test evidence
→ Known limitations
```

代码实现 PR 中不得只写“参考 PaperClaw”，必须指出具体合同、差异和验证证据。

## 7. 最小复用顺序

建议顺序：

1. Provider metadata 和 bounded retry 合同；
2. Context item / required constraint / evidence ref 合同；
3. Versioned TraceEvent 和 redaction；
4. Atomic persistence；
5. Read-only Inspector；
6. Recorded Replay；
7. Deterministic Eval；
8. SQLite Checkpointer 与 safe resume。

每一步均应独立验收，不以“迁移完整 PaperClaw 子系统”为目标。
