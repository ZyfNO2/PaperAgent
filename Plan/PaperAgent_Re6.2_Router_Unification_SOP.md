# PaperAgent Re6.2：Router Unification SOP

> **制定日期**：2026-07-11  
> **承接**：R6-1 Provider Core。  
> **周期**：4 个有效开发日。  
> **阶段门**：registry 切换真实影响新 run + 所有 structured node 使用节点专属合同 + formatter 无递归。  
> **后继**：R6-3 React Settings、R6-4 Academic Tailor 2.0。  
> **门失败时**：暂停 UI 和学术裁缝，优先修底座。

---

## 1. 目标与非目标

### 1.1 目标

将 provider registry 与生产 `llm_router` / `call_json` 统一为单一路由层。
每个 task role 拥有独立的 ModelPolicy、StructuredOutputContract 和有界 repair 策略。
每次 run 生成不可变 model policy snapshot。

### 1.2 非目标

- 不做前端 UI（R6-3 负责）；
- 不做学术裁缝 schema（R6-4 负责）；
- 不做跨域 hidden 盲测（R6-5 负责）；
- 不改变 Re5 检索链路的 Coverage Gate 逻辑；
- 不做 per-user 密钥隔离（上线前收口）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径/模块 | 格式 |
|---|---|---|---|
| D-01 | ModelPolicy schema | `app/services/router/model_policy.py` | Pydantic v2 model |
| D-02 | ResponseEnvelope schema | `app/services/router/envelope.py` | Pydantic v2 model |
| D-03 | StructuredOutputContract 注册表 | `app/services/router/contracts.py` | Python module |
| D-04 | 统一路由器 | `app/services/router/unified_router.py` | Python module |
| D-05 | 有界 repair 策略 | `app/services/router/repair.py` | Python module |
| D-06 | Run snapshot 生成器 | `app/services/router/snapshot.py` | Python module |
| D-07 | 语义校验器注册表 | `app/services/router/validators/` | Python modules |
| D-08 | 替换 `llm_router.py` + `llm.py` | 原路径 | 改造现有代码 |
| D-09 | L0 单元测试 | `apps/api/tests/test_re6/router/` | pytest |
| D-10 | L1 emulator 集成测试 | `apps/api/tests/test_re6/router/emulator/` | pytest |
| D-11 | L2 固定 replay 端到端测试 | `apps/api/tests/test_re6/router/replay/` | pytest |

---

## 3. 规范

### 3.1 允许的模型（全局约束）

**只允许使用以下两个模型（均通过 OpenCode proxy），禁止第三个模型：**

| model_id | 标识 | 适配角色 |
|---|---|---|
| `deepseek-v4-flash` | DeepSeek V4 Flash | structured_extract / search_control / formatter / rag_answer |
| `big-pickle` | Big Pickle | evidence_critic / novelty_draft / narrative_write |

- ModelPolicy 的 primary 和 fallback 只能从这两个 model_id 中选择；
- Cross-model 模式（R6.4）限定为 `deepseek-v4-flash` 生成 + `big-pickle` 审查，或反过来；
- 同模型生成与审查时必须标记 `self-review`。

### 3.2 Task Role 定义

| Task role | 典型节点 | 首要能力 | 默认 primary model | 策略 |
|---|---|---|---|---|
| structured_extract | topic_parser, verifier, dataset_extractor | 稳定 JSON | `deepseek-v4-flash` | 严格 schema，可切 formatter |
| search_control | planner, SearchController, repair | 指令遵循、短 JSON | `deepseek-v4-flash` | 低温、预算受控 |
| evidence_critic | low_bar, devils_advocate, novelty_review | 反方推理、证据约束 | `big-pickle` | 要求 evidence IDs |
| novelty_draft | innovation_extractor, 贡献写作 | 研究表达 | `big-pickle` | 不允许 first claim |
| narrative_write | narrative_builder, report phrasing | 可读性、一致性 | `big-pickle` | 不承担事实判定 |
| rag_answer | RAG QA | 引用忠实、拒答 | `deepseek-v4-flash` | 无 cited chunks 则代码拒答 |
| formatter | JSON repair | 格式服从 | `deepseek-v4-flash` | 单次、无业务判断 |

### 3.3 ModelPolicy schema

```python
class ModelPolicy(BaseModel):
    role: TaskRole
    primary: ProviderModelRef       # 只能是 deepseek-v4-flash 或 big-pickle
    fallbacks: list[ProviderModelRef] = []  # 同上，只能从这两个中选
    contract_version: str           # 如 "novelty-candidate/v1"
    temperature: float = 0.0
    allow_heuristic: bool = False
    max_provider_attempts: int = 2
    max_format_repairs: int = 1

class ProviderModelRef(BaseModel):
    provider_id: str                # OpenCode proxy provider_id
    model_id: str                   # "deepseek-v4-flash" | "big-pickle"
```

**允许的 model_id 白名单**：`["deepseek-v4-flash", "big-pickle"]`。
ModelPolicy 序列化时校验 primary 和 fallbacks 的 model_id 均在此白名单内，否则拒绝。

### 3.4 ResponseEnvelope

Provider adapter 必须先归一化为此格式，业务节点只读取 envelope：

```python
class ResponseEnvelope(BaseModel):
    provider_id: str
    model_id: str
    request_id: str
    content: str               # 主文本
    reasoning: str | None      # reasoning/thinking 字段
    tool_calls: list[dict] = []
    finish_reason: str
    usage: TokenUsage
    raw_shape: Literal["openai_chat", "anthropic_message", "custom"]

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
```

### 3.5 StructuredOutputContract

每个 structured role 注册一份合同：

```python
class StructuredOutputContract(BaseModel):
    contract_id: str                    # 如 "novelty-candidate/v1"
    task_role: TaskRole
    json_schema: dict                   # JSON Schema
    semantic_validator: str             # validator 函数名
    accepted_envelopes: list[str]       # ["content_json", "reasoning_json"]
    repair_strategy: Literal[
        "same_model_once",
        "formatter_once",
        "fallback_model_once",
        "fail"
    ]
    max_repairs: int = 1               # 硬上限，超过即 typed failure
    fallback_behavior: Literal["typed_failure", "heuristic_marked"]
```

### 3.6 有界 repair 规则

```
1. 首次输出 → schema validation
2. schema pass → semantic validation
3. schema fail → repair_strategy 决定：
   a. same_model_once: 原模型 + validator feedback 重试一次
   b. formatter_once: formatter 角色 + 节点真实 schema 重试一次
   c. fallback_model_once: 切 fallback provider 重试一次
   d. fail: 直接 typed failure
4. semantic fail → 返回任务模型一次带 validator feedback
5. 再次 fail → typed failure 或 heuristic_marked
6. repair_depth 不得超过 max_repairs（默认 1）
7. 禁止递归 formatter
```

通用 formatter 必须接收该节点的真实 schema，不能再写 verifier 专用字段。

### 3.7 Run Snapshot

每次 run 开始时生成不可变快照：

```python
class RunModelSnapshot(BaseModel):
    run_id: str
    case_id: str
    snapshot_id: str               # uuid4
    created_at: datetime
    policies: dict[TaskRole, ModelPolicy]
    provider_configs: list[dict]   # 不含 key，只有 config_version + model_id
    contract_versions: dict[str, str]
    prompt_hashes: dict[str, str]
```

**不变原则**：中途切换 provider 不改写历史 run 的 snapshot。

### 3.8 Fallback 行为

| 错误分类 | Fallback 行为 |
|---|---|
| invalid_auth | 不重试，标 profile invalid |
| permission_denied | 不重试，提示换 model |
| model_not_found | 不重试，刷新 discovery 或手填 |
| rate_limited | 有界退避（指数退避，最多 2 次）后切 fallback |
| transient_network | 有界 retry（最多 2 次）后切 fallback |
| context_too_large | 先压缩 context（记录 evidence loss），再重试 |
| malformed_output | 一次 format repair，再切 fallback |
| semantic_contract_fail | 返回任务模型一次带 validator feedback |
| 全 fallback 失败 | typed_failure 或 heuristic_marked |

所有降级在 trace 中显示最终 provider/model、错误类型、质量等级变化。

### 3.9 路由器接口

统一路由器替代 `llm_router.py` + `call_json`：

```python
async def call_with_contract(
    task_role: TaskRole,
    messages: list[dict],
    state: ResearchState,
    contract: StructuredOutputContract,
) -> ContractResult:
    """
    1. 从 RunModelSnapshot 获取 task_role 的 ModelPolicy
    2. 调用 primary provider → ResponseEnvelope
    3. schema validation → semantic validation
    4. 按 repair_strategy 有界修复
    5. 返回 ContractResult（success / typed_failure / heuristic_marked）
    """
```

`call_json` 和 `call_json_with_validation` 内部委托给 `call_with_contract`。

---

## 4. 验证

### 4.1 L0：静态合同单测

| 测试项 | 方法 | 门槛 |
|---|---|---|
| ModelPolicy schema | 构造合法/非法 policy | 非法被拒绝 |
| ResponseEnvelope schema | 构造各种 raw_shape | 正确归一化 |
| StructuredOutputContract 注册 | 注册后查询 | contract_id 唯一 |
| formatter repair_depth | 设置 max_repairs=2 尝试 | 被截断为 1 |
| formatter 无递归 | mock formatter 返回仍不合格 | 不再次调用 formatter |
| fallback chain 去重 | 设置循环 fallback | 检测并拒绝 |
| fallback 最大尝试次数 | 设置 max_provider_attempts=2 | 不超过 |
| contract 版本唯一性 | 同一 role 注册两个版本 | 只有最新生效 |
| snapshot 不可变 | 修改 provider 后查旧 run | 旧 run snapshot 不变 |

### 4.2 L1：Provider emulator 集成

| Emulator | 响应形态 | 预期 |
|---|---|---|
| openai-json | 标准 chat + content JSON | 直接通过 schema + semantic |
| reasoning-json | reasoning 有 JSON, content 有 prose | envelope 解析后通过 |
| markdown-json | fence 包 JSON | 一次 parse 后通过 |
| malformed-once | 首次缺字段, repair 后合法 | 一次 repair 后通过 |
| malformed-always | 始终不合 schema | 有界失败/切 fallback，不递归 |
| auth-429-5xx | 401/429/503 | 分类、退避/切换符合 policy |
| models-unsupported | GET models 404 | 不影响 chat 路径 |
| anthropic-like | messages/content blocks | adapter 正确归一化 |
| semantic-fail | schema pass 但 ID 不存在 | validator feedback 重试一次后 typed failure |
| all-fallback-fail | 全部 provider 失败 | typed_failure，不返回空对象 |

**P0**：
- 最终 provider/model、error class、fallback attempts 与 trace 断言完全一致；
- Silent degradation = 0%；
- Repair recursion = 0%；
- Attribution completeness = 100%（trace 有 provider/model/contract/fallback）。

### 4.3 L2：固定 replay 端到端

冻结 adapter fixture，比较基线与统一路由器：

| 场景 | 验证 |
|---|---|
| Re5 SearchController A/B/C prompts | 同一 fixture 下结果一致或更好 |
| 每个 task role 的 primary/fallback | fallback 链正确触发 |
| 创新点充分证据 | contract 通过 |
| 创新点薄弱证据 | contract 返回 needs_evidence |
| RAG 强证据 | citation 通过 |
| RAG 无命中 | 代码拒答 |

### 4.4 阶段门

- [ ] registry 选择与 production `call_with_contract` 的实际 provider 一致；
- [ ] 所有 structured node 使用节点专属 OutputContract；
- [ ] formatter 无递归、无字段污染；
- [ ] fallback 可解释，不可恢复错误不静默变成功；
- [ ] run snapshot 不可变；
- [ ] L0 100% 全绿；
- [ ] L1 全部 emulator 通过。
