# PaperAgent v0.1 开发顺序与提交规范

> Version: `v0.1`  
> Status: `IMPLEMENTATION PLAYBOOK`

## 1. 开发总原则

v0.1 只能在 `v0.1` 分支实现。旧实现从 `backup/legacy-pre-v0.1-20260716` 只读参考，不复制目录、不 cherry-pick 旧业务提交、不导入旧包。

实现顺序由依赖关系决定：

```text
文档合同
→ 测试基础设施
→ Schema
→ State/Reducer
→ Fake Providers
→ Node unit contracts
→ Router/Gate
→ Retrieval Subgraph
→ Top-level Graph
→ Checkpoint/HITL
→ OOD/Leakage
→ Optional real-provider smoke
```

## 2. 推荐 Python 与依赖边界

建议：

- Python 3.12；
- LangGraph；
- LangChain Core，仅使用 RunnableConfig/消息基础合同；
- Pydantic v2；
- pytest、pytest-asyncio、pytest-cov；
- ruff；
- mypy 或 basedpyright，二选一；
- 不在 v0.1 引入数据库 ORM、任务队列、前端框架或多 Agent 框架。

具体版本在实现首个提交时锁定，并记录于 `pyproject.toml`。

## 3. 目标目录

```text
src/paperagent/
├── __init__.py
├── version.py
├── config.py
├── errors.py
├── state.py
├── context.py
├── graph.py
├── nodes/
│   ├── __init__.py
│   ├── intake.py
│   ├── planning.py
│   ├── evidence_synthesis.py
│   ├── method_design.py
│   ├── quality_gate.py
│   ├── human_review.py
│   ├── report.py
│   └── persist.py
├── retrieval/
│   ├── __init__.py
│   ├── graph.py
│   ├── prepare_search.py
│   ├── search_tool.py
│   ├── verify_evidence.py
│   └── gate.py
├── schemas/
│   ├── __init__.py
│   ├── common.py
│   ├── request.py
│   ├── plan.py
│   ├── evidence.py
│   ├── method.py
│   ├── quality.py
│   ├── report.py
│   └── trace.py
├── prompts/
│   ├── registry.py
│   └── v0_1/
│       ├── planning.md
│       ├── evidence_synthesis.md
│       ├── method_design.md
│       └── report.md
├── providers/
│   ├── base.py
│   ├── fake_llm.py
│   ├── fake_search.py
│   ├── llm_adapter.py
│   └── search_adapter.py
├── telemetry/
│   ├── events.py
│   ├── recorder.py
│   └── hashing.py
└── persistence/
    ├── base.py
    └── memory.py
```

测试目录：

```text
tests/
├── conftest.py
├── unit/
├── contracts/
├── nodes/
├── graph/
├── integration/
├── ood/
└── fixtures/
    ├── llm/v0_1/
    ├── search/v0_1/
    └── states/v0_1/
```

## 4. WP0 — 测试工具链

### RED

先创建失败测试：

- package 不可导入；
- 版本常量缺失；
- fixture loader 缺失；
- unknown fixture key 未报错；
- test clock/id factory 缺失。

### GREEN

只实现：

- 最小 package；
- pytest 配置；
- FakeClock；
- FakeIdFactory；
- FixtureKey/Loader；
- 基础 lint/typecheck 配置。

### 提交

```text
test(v0.1): define test infrastructure contracts
chore(v0.1): initialize package and test infrastructure
```

## 5. WP1 — Schema

实现顺序：

1. common IDs/enums；
2. RunContext/Budgets；
3. ResearchRequest；
4. ResearchPlan；
5. Evidence；
6. Synthesis；
7. Method；
8. Quality；
9. Report；
10. Trace。

每个 schema 先提交失败测试，再提交实现。

```text
test(v0.1): define research plan schema invariants
feat(v0.1): implement research plan schema
```

## 6. WP2 — State 与 Reducer

### 测试先行

- trace append；
- artifact replace；
- input state 不变；
- evidence stable merge；
- JSON round trip；
- forbidden deep merge。

### 实现

- `PaperAgentState`；
- StatePatch typing；
- reducer；
- semantic validators。

## 7. WP3 — Provider Contracts

### LLMProvider

先定义 Protocol 和 contract tests，再实现 Fake Provider。

必须传入显式 `task` 和 `scenario`。生产 adapter 可忽略 scenario，但测试 Fake 不允许从 Prompt 推断。

### SearchProvider

先定义 query/result/error schema，再实现 Fake Search。

### Provider Metadata

统一：

```text
provider
model/tool name
request_id
attempt
latency_ms
input_tokens
output_tokens
finish_reason
```

## 8. WP4 — Trace 与 Error

先测试：

- node start/completed/failed；
- route decided；
- provider metadata；
- payload hash；
- secret redaction；
- error serialization；
- event order。

实现不得依赖 LangSmith。

## 9. WP5 — Node 实现顺序

每个节点使用同一小循环：

1. 写 happy-path 失败测试；
2. 写 invalid-input 失败测试；
3. 写 provider/error 失败测试；
4. 写 trace 失败测试；
5. 实现最少代码；
6. 补 semantic validation；
7. 重构 Context projection。

顺序：

```text
intake
→ planning
→ prepare_search
→ search_tool
→ verify_evidence
→ evidence_synthesis
→ method_design
→ quality_gate
→ report
→ persist
→ human_review
```

## 10. WP6 — Retrieval Subgraph

先写路径测试：

- enough first round；
- retry second round；
- budget exhausted；
- empty queries；
- partial tool failure；
- no third round。

然后组装 Subgraph。禁止先组图再猜边界。

## 11. WP7 — Top-level Graph

先写完整 graph test，以 deterministic node stubs 验证拓扑。随后逐个替换为真实节点。

推荐顺序：

```text
compiled graph with stubs
→ success path
→ planning branches
→ quality branches
→ retrieval subgraph integration
→ persist
→ interrupt/resume
```

每次替换一个节点，完整 graph tests 必须保持绿色。

## 12. WP8 — Checkpoint 与 HITL

先使用 MemorySaver 或自有 InMemoryCheckpointer 建立合同：

- thread_id 必需；
- interrupt 前状态可读取；
- resume 不重复已完成副作用；
- resume 后继续预期边；
- checkpoint 不包含 Provider 实例和 secret。

SQLite/Postgres 不属于 v0.1 必需范围。

## 13. WP9 — OOD 与 Leakage

在接真实 Provider 前完成：

- OOD 输入 fixtures；
- legacy 禁止实体词表；
- Prompt 静态扫描；
- fixture 静态扫描；
- output semantic scan；
- impossible/underspecified routes。

## 14. WP10 — Real Provider Smoke

仅在离线测试全部通过后：

- 实现一个真实 LLM adapter；
- 实现一个真实 Search adapter 或暂时保持 Fake Search；
- 运行最小 smoke；
- 标记为非确定性；
- 不进入默认 CI；
- 不调整离线 fixture 来迎合真实模型输出。

## 15. Prompt 开发规则

Prompt 是生产代码，必须测试：

- registry key 唯一；
- prompt_version 固定；
- schema instructions 存在；
- 不包含 fixture 答案；
- 不包含旧项目专有实体；
- 不要求输出隐藏 CoT；
- 明确只能引用提供的 Evidence IDs；
- blocked/unknown 行为明确。

Prompt 变化需要 contract test 和版本更新。

## 16. Commit 粒度

允许：

```text
test(v0.1): define planning happy path
feat(v0.1): implement planning node minimum path
test(v0.1): add planning schema failure cases
fix(v0.1): reject unknown planning fields
refactor(v0.1): extract planning context projection
```

禁止：

```text
feat: implement all agents and tests
fix tests
update everything
```

单个提交应能明确回答：新增了哪个合同、哪段最小实现、哪些测试证明它。

## 17. PR/Review Checklist

- [ ] 测试先于实现；
- [ ] 新行为有 RED 证据；
- [ ] 无旧代码导入；
- [ ] 无 Prompt/fixture 答案泄漏；
- [ ] State patch 字段最小；
- [ ] 错误不静默 fallback；
- [ ] Trace 包含版本和路由；
- [ ] 循环有硬上限；
- [ ] Fixture key 显式；
- [ ] 文档同步；
- [ ] 全部离线测试通过。

## 18. 开发停止条件

出现以下任一情况，停止编码并修订文档：

- 需要新增未设计节点；
- 一个节点需要读取大部分 State；
- Fake Provider 必须解析 Prompt 才能工作；
- repair 次数无法硬限制；
- 真实 Provider 行为迫使 schema 大幅漂移；
- 需要复制旧项目大量代码；
- 测试只能通过降低断言；
- Graph 路由无法用确定性 fixture 重现。
