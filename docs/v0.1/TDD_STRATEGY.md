# PaperAgent v0.1 TDD 策略

> Version: `v0.1`  
> Status: `MANDATORY DEVELOPMENT POLICY`

## 1. 目的

TDD 在 v0.1 中用于约束架构，而不仅是提高覆盖率。测试必须先定义：

- 每个节点可读取和可写入的 State 字段；
- 每条条件边的判定规则；
- LLM 中间回复的结构和失败模式；
- 检索循环、repair 和 HITL 的硬上限；
- Trace、Checkpoint 和 Provider 的可观测行为；
- 域外输入下不得出现旧测试案例答案。

## 2. 强制循环

每个最小行为单元执行：

### RED

- 先新增一个失败测试；
- 测试名称描述业务合同，而非实现细节；
- 确认失败原因正是缺少目标行为；
- 禁止因 import error 以外的无关原因失败。

### GREEN

- 写最少生产代码让新增测试通过；
- 不提前实现后续需求；
- 不加入未测试 fallback；
- 不重构无关模块。

### REFACTOR

- 删除重复；
- 收窄接口；
- 保持所有测试绿色；
- 不通过放宽断言掩盖回归。

## 3. 测试层级

```text
Unit
  ↓
Schema / Provider Contract
  ↓
Node Contract
  ↓
Router / Gate
  ↓
Subgraph
  ↓
Full Graph Integration
  ↓
OOD / Leakage
  ↓
Optional Real Provider Smoke
```

### Unit

无网络、无真实模型、无真实时间和随机性。

### Contract

验证接口而非 SDK 实现：

- `LLMProvider.generate_structured(...)`；
- `SearchProvider.search(...)`；
- Prompt registry；
- Fixture loader；
- Checkpointer serialization。

### Node

直接调用单个 node，并断言：

- 返回的是增量 patch；
- 不修改输入 state；
- 只写允许字段；
- 正确调用 Provider；
- 正确写 Trace；
- 错误类型稳定。

### Graph

使用 Fake Providers 运行真实 LangGraph compiled graph，并断言节点序列、路由、调用预算和终止状态。

### OOD

检测领域外问题和旧案例实体泄漏。

## 4. Test Doubles

### 4.1 FakeLLMProvider

Fake LLM 是有状态、可检查调用历史的确定性实现：

```python
class FakeLLMProvider:
    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[BaseModel],
        messages: list[Message],
    ) -> BaseModel:
        ...
```

必须支持：

- 固定 fixture 返回；
- malformed JSON；
- schema violation；
- timeout；
- transient failure；
- permanent failure；
- 调用历史；
- token/latency 假 metadata；
- 未知 fixture key 立即失败。

禁止：

- 根据 Prompt 内容选择回复；
- 自动生成缺失 fixture；
- 对未知任务返回通用成功；
- 在测试中调用真实模型。

### 4.2 FakeSearchProvider

键：

```text
scenario + query_id + call_index + fixture_version
```

支持：成功、空结果、重复结果、部分失败、timeout、invalid locator。

### 4.3 FakeClock / FakeIdFactory

所有时间戳和 ID 固定，保证 snapshot 和 hash 可重复。

### 4.4 InMemoryCheckpointer

用于 interrupt/resume 和状态序列化测试，不模拟数据库性能。

## 5. Fixture 版本管理

Fixture 不是随意测试数据，而是版本化开发合同。

```text
fixture_version: v0.1
schema_version: 0.1
scenario: happy_path
producer: test-contract
```

规则：

- 修改 fixture schema 必须同步修改合同测试；
- 不能覆盖旧 fixture 来掩盖回归；
- 行为变化新增 scenario 或版本；
- fixture 中的 Evidence ID 必须稳定；
- fixture 不得包含旧 PaperAgent 测试集专有实体，除专门的 leakage negative case。

## 6. 测试命名

格式：

```text
test_<unit>__<condition>__<expected_behavior>
```

示例：

```text
test_planning_node__need_human_fixture__returns_clarification_plan
test_quality_gate__unknown_evidence_id__routes_repair_method
test_retrieval_graph__second_round_exhausted__terminates_without_third_search
test_report_node__blocked_quality__includes_limitations
test_fake_llm__unknown_fixture_key__fails_loudly
```

## 7. 每个节点的最低测试模板

```python
@pytest.mark.asyncio
async def test_node__happy_path__returns_expected_patch(): ...

@pytest.mark.asyncio
async def test_node__invalid_input__raises_typed_error(): ...

@pytest.mark.asyncio
async def test_node__provider_timeout__records_failure_trace(): ...

@pytest.mark.asyncio
async def test_node__same_input_twice__is_deterministic(): ...

@pytest.mark.asyncio
async def test_node__execution__does_not_mutate_input_state(): ...
```

LLM 节点额外要求：

```python
test_node__unknown_evidence_id__fails_semantic_validation
test_node__malformed_response__does_not_use_silent_fallback
test_node__happy_path__uses_expected_task_and_fixture_key
test_node__response__stores_prompt_and_schema_versions_in_trace
```

## 8. Router 和 Gate 测试

Router/Gate 使用参数化表驱动测试：

```python
@pytest.mark.parametrize(
    ("input_status", "expected_route"),
    [
        ("ready", "retrieval_subgraph"),
        ("need_human", "human_review_node"),
        ("blocked", "report_node"),
    ],
)
def test_planning_route(...): ...
```

质量门必须覆盖：

- pass；
- repair_retrieval；
- repair_method；
- human_review；
- blocked；
- unknown reason code；
- repair budget exhausted；
- identical input returns identical verdict。

## 9. Graph TDD 顺序

先写以下 graph tests，之后才实现图：

1. `happy_path`；
2. `planning_need_human`；
3. `planning_blocked`；
4. `retrieval_retry`；
5. `retrieval_exhausted`；
6. `repair_method`；
7. `repair_retrieval`；
8. `provider_timeout`；
9. `checkpoint_resume`；
10. `budget_hard_stop`。

每个测试断言：

- visited node sequence；
- LLM call count；
- Search call count；
- terminal status；
- final artifact；
- route Trace；
- 无第三轮 retrieval；
- 无第二次 method repair。

## 10. 语义验证测试

Pydantic 只能验证结构，以下由 semantic validator 测试：

- Evidence ID 是否存在；
- query gap_id 是否存在；
- accepted/rejected 状态是否混用；
- report 是否引入新 locator；
- method status 是否错误标记 verified；
- completed report 是否缺 limitations；
- hypothesis 是否缺 metric/threshold；
- repair target 是否和 reason code 一致。

## 11. Leakage / OOD 测试

维护禁止泄漏词表，仅用于测试扫描：

```text
legacy fixture entities
legacy paper titles
legacy dataset names
legacy hard-coded baselines
```

要求：

- 普通 OOD 输入输出不得出现禁止实体；
- 只有输入或 accepted evidence 明确包含时才允许出现；
- Prompt template、fallback 和 fixture 均接受静态扫描；
- 测试不能通过简单替换大小写绕过。

## 12. 覆盖率要求

覆盖率不是唯一指标，但作为最低门禁：

| 范围 | 最低 line coverage | branch coverage |
|---|---:|---:|
| schemas / validators | 95% | 90% |
| routers / gates | 100% | 100% |
| nodes | 90% | 85% |
| retrieval subgraph | 90% | 90% |
| full graph orchestration | 85% | 85% |
| overall | 90% | 85% |

禁止使用 `pragma: no cover` 排除核心业务路径。

## 13. CI 测试组

```text
lint
unit
contracts
graph
integration
ood
coverage
```

默认 CI 不执行：

```text
real_provider
network
slow_external
```

## 14. Bug 修复规则

任何 Bug：

1. 先提交可复现失败测试；
2. 再提交最小修复；
3. 必要时新增 fixture scenario；
4. 不修改既有预期来适配错误行为；
5. 在 changelog 或 PR 中记录根因和防回归测试。

## 15. Definition of Done

一个工作包只有在以下条件全部满足时完成：

- 新测试先于实现；
- 新增行为有 happy/error/boundary 测试；
- 全套离线测试通过；
- 无网络依赖；
- fixture 可重复；
- Trace 可断言；
- 文档和实现一致；
- 代码审查可指出 RED、GREEN、REFACTOR 三阶段证据。
