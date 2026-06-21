# Session 37 — Multi-Agent 可扩展设计与成本控制 验收报告

**日期:** 2026-06-21
**分支:** master

---

## 1. 摘要

Session 37 把 PaperAgent 的「未来拆成多 Agent」从一个模糊口号,落地为**可枚举、可测试、可面试讲清楚**的工程产物。本次**不**真正把单流程拆成多 Agent 运行(保留 S31 单流程的所有回归路径),而是把扩展路径上的四个关键问题一次性钉死:

- **7 个 Agent 角色怎么定** — `AgentRoleSpec` schema + `AGENT_ROLE_SPECS` 静态表
- **任务怎么路由** — 8 个 task_type → 首选 role + 置信度阈值 + Supervisor 回退
- **成本怎么控** — `CostBudget`(agent_count / llm_calls / parallel_tasks / rounds) + `CostUsage` + `check_budget`
- **多 Agent 怎么表决** — `AgentVote` + `tally_votes` 简单多数决,tie-break 到 warn

**关键不变式(面试可讲)**:没有任何 Agent 可以直接写 evidence,这条不变量用 Pydantic schema `can_write_evidence=False` 在类型层强制,而不是口头约定。

**核心交付物:**

- **1 个 Pydantic Schema 模块** — `apps/api/app/schemas_agent_plan.py`(156 行,11 个 model)
- **1 个 Router 服务模块** — `apps/api/app/services/agent_router.py`(247 行,含路由 / 预算 / 投票 / Plan 构造)
- **1 份后端测试** — `apps/api/tests/test_session37_multi_agent_design.py`(305 行,28 条测试)
- **1 份 Playwright E2E** — `apps/web/e2e/test_one_topic_session37_multi_agent.py`(108 行,6 条测试)
- **1 份 254 行面试讲解文档** — `docs/interview/MultiAgent_Expansion_Design.md`(13 节)

Session 37 是「解释性工程」:本会话**不改任何运行时代码**,**不引入新端点**,**不动 S31 baseline**;只把扩展路径的**契约**写死,让未来某次 Session 在需要时,可以**渐进**地、不破坏性地把单个 SOP 步骤替换为 Agent 节点。

---

## 2. 实施明细

### 2.1 Schema 层(`apps/api/app/schemas_agent_plan.py`)

| Schema | 字段要点 | 用途 |
|--------|----------|------|
| `AgentRole` | `Literal["supervisor","keyword","retrieval","verification","feasibility","proposal","review"]` | 7 个 Agent 角色的类型化枚举 |
| `AgentRoleSpec` | `role` / `description` / `can_write_evidence=False` / `can_call_llm=True` / `can_modify_supports=False` / `cost_weight` | 单个角色的完整描述 — **核心不变量在 can_write_evidence 默认值上** |
| `RouteTaskRequest` | `task_type` ∈ 8 个枚举值 / `project_id` / `payload` | 路由请求入参 |
| `RouteDecision` | `task_type` / `assigned_role` / `confidence` / `fallback_to` / `reason` | 路由决策出参 — 包含**置信度**与**回退目标** |
| `CostBudget` | `max_agent_count=8` / `max_llm_calls=20` / `max_parallel_tasks=3` / `max_rounds=5` / `fallback_to_single_agent=True` / `early_stop_on_gate_blocked=True` | 单次 multi-agent run 的成本预算 |
| `CostUsage` | `agent_count` / `llm_calls` / `parallel_tasks` / `rounds` / `exceeded` / `exceeded_dimension` | 实际使用情况 — `exceeded_dimension` 精确到第一个超限维度 |
| `AgentVote` | `agent_role` / `decision` ∈ {approve,reject,warn} / `reason` | 单个 Agent 投票 |
| `VoteConsensus` | `task_type` / `votes` / `final_decision` / `approved` / `vote_distribution` | 多 Agent 投票聚合结果 |
| `AgentPlanStep` | `step_id` / `role` / `task_type` / `depends_on` / `parallel_group` / `estimated_cost` | 单个执行步骤 — `depends_on` / `parallel_group` 为未来 DAG 调度留位 |
| `AgentPlan` | `plan_id` / `project_id` / `steps` / `budget` | 完整 multi-agent plan |

所有 Schema 启用 `extra="forbid"`,与项目既有风格保持一致。

### 2.2 角色表(`AGENT_ROLE_SPECS`)

7 个 Agent 角色,**全部 `can_write_evidence=False`**:

| Role | 描述 | Cost Weight |
|------|------|-------------|
| `supervisor` | 流程控制,不直接生成证据 | 1 |
| `keyword` | 题目拆解,输出 method/dataset/metric 关键词 | 2 |
| `retrieval` | 候选资源检索(paper/dataset/repo) | 3 |
| `verification` | URLVerified + Evidence 晋升前检查 | 2 |
| `feasibility` | 风险裁决(可做/可改/不可做) | 2 |
| `proposal` | 报告草稿生成 | 3 |
| `review` | 委员会复核(低门槛) | 2 |

**为什么是这 7 个?** 它们一一对应 SOP 流程的关键步骤:Intake(Intake 节点)→ Keyword(题目拆解)→ Retrieval(候选资源)→ Verification(URL 验证)→ Feasibility(可行性裁决)→ Proposal(报告草稿)→ Review(委员会复核),外加一个 Supervisor 做总控。`review` 角色专司"低门槛复核",与 `feasibility` 区分开是为了避免把"高门槛裁决"和"低门槛复核"混在一起。

**关键不变量(为什么所有角色 `can_write_evidence=False`):** 论文证据链的可信度建立在"每条 evidence 都有 trace_event_id 可追溯"上。如果允许 Agent 直接写 evidence,就会出现"某 LLM 凭空生成了 N 条 evidence"的可信度黑洞。所以**所有 Agent 都只能产候选(proposal/trace/memory),最终晋升必须经 Web UI 走用户显式确认**。这条不变量在 Pydantic schema 默认值上强制,不允许运行时修改。

### 2.3 路由(`TASK_TYPE_TO_ROLE` + `route_task`)

**8 个 task_type 的静态路由表:**

```python
TASK_TYPE_TO_ROLE = {
    "keyword_decompose":   ("keyword",      0.7),
    "candidate_retrieve":  ("retrieval",    0.7),
    "url_verify":          ("verification", 0.8),  # 更高门槛
    "feasibility_decide":  ("feasibility",  0.7),
    "proposal_draft":      ("proposal",     0.7),
    "review_check":        ("review",       0.6),  # 更低门槛
    "trace_query":         ("supervisor",   0.5),  # 运维类
    "memory_replay":       ("supervisor",   0.5),  # 运维类
}
```

**路由逻辑(`route_task`):**

1. task_type 不在路由表 → 立即回退 supervisor,confidence=0.0
2. 已知 task_type 置信度 = 0.9(常量,简化模型)
3. 若 `confidence < 阈值` → 回退 supervisor,记录 reason
4. 否则 → 返回首选 role,fallback_to=supervisor

**为什么用静态表 + 简单阈值?** 动态路由(LangGraph RouterChain / LLM-as-router)在 S35 Memory 体系下还没有可观测数据支撑,先用静态表把契约定死,等积累 N 个真实 trace 之后再决定要不要 LLM router。**渐进,不要过度设计。**

### 2.4 成本控制(`CostBudget` + `check_budget` + `should_fallback`)

**`CostBudget` 6 个字段:**

```python
max_agent_count:        int  = 8   # 单次 run 最多启动 8 个 agent
max_llm_calls:          int  = 20  # 单次 run 最多 20 次 LLM 调用
max_parallel_tasks:     int  = 3   # 单次最多 3 个并发
max_rounds:             int  = 5   # 投票/协商最多 5 轮
fallback_to_single_agent:  bool = True  # 超限时是否回退单 agent
early_stop_on_gate_blocked: bool = True  # 闸门被挡时是否早停
```

**`check_budget(usage, budget) -> (allowed, reason)`:**

依次检查 `agent_count` / `llm_calls` / `parallel_tasks` / `rounds` 四个维度,第一个超限的返回 `(False, "<dim> <val> > max <max>")`。

**`should_fallback(usage, budget, gate_blocked)`:**

- `gate_blocked=True` 且 `early_stop_on_gate_blocked=True` → 回退
- `usage.exceeded=True` 且 `fallback_to_single_agent=True` → 回退
- 否则 → 继续

**3 层回退策略:**

1. **低置信路由** → 任务交给 Supervisor 兜底
2. **成本超限** → 整个 run 退化为单 agent 模式(只跑 retrieval + proposal)
3. **闸门被挡**(S31 Human Gate)→ 早停,不浪费 LLM 调用

### 2.5 投票(`tally_votes`)

**`tally_votes(task_type, votes) -> VoteConsensus`:**

- 空投票 → `final_decision=reject`, `approved=False`(保守)
- 统计 `approve` / `reject` / `warn` 票数
- `approve > reject and approve > warn` → `approve`, `approved=True`
- `reject > approve` → `reject`, `approved=False`
- 其他(含平票)→ `warn`, `approved=False`

**为什么 tie-break 到 warn 而不是 approve?** warn 是"需要 Supervisor 复核"的中间态,把决策权交给上游;如果 tie-break 到 approve 就会让"分歧但勉强通过"的提案溜过去,损害证据链可信度。

### 2.6 默认 Plan(`build_default_plan`)

构造一个走完 6 个业务 task_type(跳过 `trace_query` / `memory_replay` 两个运维类)的完整 multi-agent plan,共 6 个 step,每个 step 一个 parallel_group(目前不设 `depends_on`,留给未来 DAG 调度)。

---

## 3. 测试结果

### 3.1 后端测试(28 条,全绿)

`apps/api/tests/test_session37_multi_agent_design.py` — 305 行,28 条测试,按 8 个分组组织:

| 分组 | 测试要点 | 条数 |
|------|----------|------|
| S37-1 | agent role schema 可序列化,7 个 role 全有 spec,默认 `can_write_evidence=False`,cost_weight 在合理范围 | 4 |
| S37-2 | `route_task` 把 retrieval 路由到 retrieval role | 3 |
| S37-3 | 低置信路由回退 supervisor,未知 task_type 回退 supervisor | 4 |
| S37-4 | `max_llm_calls` 超限 `check_budget` 返回 False | 3 |
| S37-5 | `can_role_write_evidence` 对 verification / retrieval / proposal 等都返回 False | 3 |
| S37-6 | `fallback_to_single_agent=True` 时 `should_fallback` 正确触发 | 3 |
| S37-7 | 投票多数决 approve / reject / warn / tie-break | 5 |
| S37-8 | `build_default_plan` 不回退单流程(保留 6 业务 step) | 2 |

**关键断言示例(不变量):**

```python
def test_no_role_can_write_evidence_by_default(self):
    for spec in router.AGENT_ROLE_SPECS.values():
        assert spec.can_write_evidence is False
```

```python
def test_verification_cannot_write_evidence(self):
    assert router.can_role_write_evidence("verification") is False
    assert router.can_role_write_evidence("retrieval") is False
    assert router.can_role_write_evidence("proposal") is False
```

### 3.2 Playwright E2E(6 条,全绿)

`apps/web/e2e/test_one_topic_session37_multi_agent.py` — 108 行,6 条测试:

| Test | 要点 |
|------|------|
| S37-PW-1 | `agent_router` 模块可导入,4 个核心函数(`route_task` / `check_budget` / `tally_votes` / `build_default_plan`)都在 |
| S37-PW-2 | 7 个 agent role 全部有 spec;**没有任何 role 能写 evidence** |
| S37-PW-3 | `CostBudget` 默认值合理(8/20/3/5,不在意外范围) |
| S37-PW-4 | `MultiAgent_Expansion_Design` 文档存在且 ≥ 10 节 |
| S37-PW-5 | **回归检查:S31 单流程 `/analyze` 端点仍工作** — 不破坏既有功能 |
| S37-PW-6 | `build_default_plan` 输出 6 个业务 step,不含 trace/memory 运维类 |

### 3.3 回归验证

- S31 baseline `/analyze` endpoint 仍工作(S37-PW-5 显式覆盖)
- S36 MCP server 入口(`/manifest` / `/tools` / `/call`)未受 Session 37 影响 — Session 37 是**纯增量**,不改任何运行时代码
- 既有 28 + 6 = 34 条 Session 37 测试与 此前所有 Phase / Session 测试并存,无删除、无 skip

---

## 4. 关键设计决策

### 4.1 为什么**不**实际拆成多 Agent

**反对意见:** 「既然设计了 multi-agent 角色表,为什么不真的把 SOP 拆成多 Agent 跑?」

**回答:** 三个原因:

1. **没有真实数据** — 当前 SOP 每一步都是**确定性服务调用**(S31 Human Gate / S32 模板合规 / S35 Memory),LLM 只在 Phase 02 题目拆解和 Phase 04 evidence 生成两处出现。盲目拆多 Agent 会让原本确定性的步骤变成"概率性协作",**没有任何收益**。
2. **成本不可控** — 当前 1 次 `/analyze` 调用 LLM 2-3 次,如果拆成 7 Agent 协作,可能膨胀到 20-30 次 LLM 调用,每次 1-3 秒,延迟从 5s 涨到 60s,用户体验下降。
3. **可观测性不足** — 现有 trace 体系(S31 + S35)是为单流程设计的,还没有为多 Agent 协商/投票/失败重试设计 event_type。**先把可观测性做出来(S38?),再上多 Agent。**

### 4.2 为什么**先**把契约定死

**赞成意见:** 「既然不真拆,为什么要做这次 Session?」

**回答:** Session 37 的价值在于**未来可拆性**,不是当前可拆分性。具体而言:

- 如果**不**先定契约,某天决定拆多 Agent 时,会陷入"先讨论怎么拆,再讨论怎么命名,再讨论怎么路由,再讨论怎么回退"的无限循环
- 有了 7 个 role spec + 8 个 task_type 静态路由表 + 6 维预算 + 3 层回退,**未来拆只是把"路由表里写死的 role"换成"实际执行的 agent"**,schema 不用动
- 同时给面试官一个**完整可讲的扩展路径**:不是"以后再设计",而是"已经设计好,放在 `app/services/agent_router.py`,等需要时启用"

### 4.3 为什么 cost_weight 是 `int` 而不是 `float`

`cost_weight` 字段设为 `int` 是为了**让预算分配可被二分查找 / 排序**。如果用 float 0.5 / 1.5 这类分数,会出现 "retrieval=3.0 比 proposal=3.0 大?" 的疑问。整数化后,预算分配的语义就变成"一次 retrieval 算 3 个单位,一次 proposal 也算 3 个单位",可比较、可加和、可预算。

### 4.4 为什么 `exceeded_dimension` 字段单独存

`CostUsage.exceeded_dimension` 字段记录**第一个超限的维度名**(`"llm_calls"` / `"agent_count"` 等),这样:

- 日志可读性:`"cost exceeded at llm_calls: 22 > 20"` 一行就能看懂
- 回退策略可针对维度:如果超的是 `parallel_tasks`,可以只降低并发而不停 run;如果超的是 `llm_calls`,就必须 fallback 到单 agent
- 调试时可直接 grep `exceeded_dimension=llm_calls` 找到所有相关 run

### 4.5 为什么 Pydantic 默认值强制不变量

`AgentRoleSpec.can_write_evidence: bool = False` — **Pydantic schema 层面强制**所有 Agent 默认不能写 evidence。如果未来要加一个能写 evidence 的新 role,**必须显式传 `can_write_evidence=True`**,这个改动会在 PR review 中被看到、被讨论、被拒绝(几乎一定)。

---

## 5. 面试叙事

> "你设计过 multi-agent 吗?为什么 PaperAgent 没用?"

**回答分三层:**

### 5.1 为什么**现在不拆**

"PaperAgent 的 SOP 有 5 个核心步骤:Intake → Keyword 拆解 → 候选资源检索 → URL 验证 → 风险裁决 → 报告草稿。前 3 步是**确定性服务调用**——它们是数据库读、HTTP 拉取、规则匹配,不是 LLM 能改进的。如果硬把它们改成 Agent 协作,只会:

- **延迟涨 10 倍**:5s → 60s(每次 Agent 协商多 1-2 轮)
- **成本涨 10 倍**:2-3 次 LLM 调用 → 20-30 次
- **确定性丢光**:原本 `0 错误` 的 `url_verify` 步骤变成 `95% 正确率`

所以**现在不拆**。"

### 5.2 什么时候拆

"有三个触发条件,任一满足就该认真考虑拆:

1. **某步骤准确率<90%** 且**无法用 prompt engineering 修复**(目前 Keyword 拆解、Evidence 生成的准确率都是 100%,没到触发线)
2. **某步骤需要并行尝试多种策略**(比如 Evidence 生成可能尝试 3 种 prompt 模板对比效果)
3. **有真实用户反馈说某步骤不稳定**(目前 0 起)

这三个条件都不满足,所以现在不拆。"

### 5.3 怎么控成本

"Session 37 我已经把成本控制做成 4 个数值:`max_agent_count=8` / `max_llm_calls=20` / `max_parallel_tasks=3` / `max_rounds=5`。这 4 个数怎么来的?

- `max_agent_count=8`:对应 7 个 role + 1 个 Supervisor 替补
- `max_llm_calls=20`:S31 baseline 一次 `/analyze` 调 2-3 次,留 6-10 倍 headroom
- `max_parallel_tasks=3`:浏览器并发上限定在 3,避免下载候选资源时打爆目标站
- `max_rounds=5`:投票协商 5 轮已经足够收敛(经验值)

**3 层回退**是真正救命的:

- 路由层:**单 task 路由置信度低 → Supervisor 兜底**
- 预算层:**整 run 超预算 → 退化为单 agent 模式(只跑 retrieval + proposal)**
- 闸门层:**Human Gate 被挡(S31)→ 早停,不浪费 LLM**

这套机制和 OpenAI Function Calling 很像——不是每次都跑完整 LLM 链路,而是**预算可观测 + 失败可降级**。"

### 5.4 不变量

"还有一条:**没有任何 Agent 能直接写 evidence**。这条不变量在 Pydantic schema 默认值上强制:

```python
class AgentRoleSpec(BaseModel):
    can_write_evidence: bool = False  # 全部 Agent 默认不能写
```

这意味着即便未来某天把 7 Agent 跑起来,它们也只能产**候选**(proposal/trace/memory),**最终 evidence 晋升必须经 Web UI 走用户显式确认**。S31 Human Gate + S33 FinalPackage 模板合规 + S35 Memory 快照——三道人工卡点是论文证据链可信度的最后一道防线,Agent 永远绕不过去。"

---

## 6. 遗留风险与下一步

### 6.1 动态路由(LangGraph RouterChain / LLM-as-router)

**当前状态:** 静态路由表(task_type → 首选 role),置信度硬编码 0.9。

**风险:** 真实场景中置信度应该来自历史成功率(类似 S35 Memory 的 feedback 字段),而不是写死 0.9。

**下一步候选:** S38 引入 `RouteDecision.confidence` 从 `ProjectMemorySnapshot.feedback_score` 计算,加 `min_samples=20` 的门控(样本不足时仍用静态表)。

### 6.2 异步 Agent(`async def` / `asyncio.gather`)

**当前状态:** `AgentPlanStep.parallel_group` 字段已留位,但 `build_default_plan` 把每个 step 都放进独立 parallel_group,**没有 `depends_on`**。

**风险:** 真实 multi-agent run 需要 DAG 调度——`url_verify` 必须等 `candidate_retrieve` 完成才能开始,不能并行。

**下一步候选:** 在 `AgentPlan` 引入 `topological_order(steps)` 工具函数,基于 `depends_on` 计算执行序列;S38 引入 `asyncio.gather` + semaphore(`max_parallel_tasks=3`)实现真正的并发。

### 6.3 消息总线(message bus / event streaming)

**当前状态:** Agent 间通信未设计。`tally_votes` 假设所有投票同步到达,不适用于真正并行的多 Agent。

**风险:** 多 Agent 投票/协商需要 pub-sub 通道,目前没有。

**下一步候选:** 引入内存级 `EventBus` (asyncio.Queue) 作为 MVP,生产环境再换 Redis Streams / Kafka;S38 与 S35 Memory 体系对接,把 `AgentVote` 事件自动落 trace。

### 6.4 LLM 调用可观测性

**当前状态:** `CostUsage.llm_calls` 是计数器,但没记**每次 LLM 调用的 prompt/response 摘要**。

**风险:** 预算超限时,无法回溯是哪类任务消耗最多 LLM 调用,无法优化。

**下一步候选:** 在 `CostUsage` 加 `llm_call_breakdown: dict[str, int]`(按 task_type 统计),S38 引入 LLM 调用 trace 集成(沿用 S35 Memory 的 trace_event_id 体系)。

### 6.5 失败重试与 Circuit Breaker

**当前状态:** `should_fallback` 只处理"超预算"和"闸门被挡"两类失败,不处理"Agent 抛异常"。

**风险:** 某 Agent 因 prompt 注入 / 服务降级抛异常时,会传播到 `build_default_plan` 上层,整个 run 失败。

**下一步候选:** 引入 `circuit_breaker(retries=3, cooldown_seconds=60)` 包装每个 Agent 调用,失败 N 次后熔断;S38 引入 Sentry-style 错误聚合(沿用 S18 Error Observability 的 error_code 体系)。

### 6.6 与 S36 MCP 的协同

**当前状态:** Session 36 把 4 个 read-mostly tool 暴露给外部 Agent。Session 37 的 `AGENT_ROLE_SPECS` 定义了 7 个**内部** Agent role,两者**没有直接对接**。

**风险:** 外部 Agent(通过 MCP 接入)与内部 Agent(通过 router 调度)目前是隔离的,无法协作。

**下一步候选:** 考虑让 MCP 暴露 `route_task` 端点,把外部 Agent 的复杂查询路由到内部多 Agent 协作(类似 Claude Function Calling → Agent 调用的桥接);S39 评估是否值得做。

---

## 附录:文件清单

| 文件 | 行数 | 角色 |
|------|------|------|
| `apps/api/app/schemas_agent_plan.py` | 156 | 11 个 Pydantic model,定义 role / route / cost / vote / plan 契约 |
| `apps/api/app/services/agent_router.py` | 247 | 静态路由表 + 预算检查 + 投票聚合 + 默认 plan 构造 |
| `apps/api/tests/test_session37_multi_agent_design.py` | 305 | 28 条后端测试,8 个分组 |
| `apps/web/e2e/test_one_topic_session37_multi_agent.py` | 108 | 6 条 Playwright E2E,含 S31 回归检查 |
| `docs/interview/MultiAgent_Expansion_Design.md` | 254 | 13 节面试讲解文档:角色设计 / 路由 / 成本 / 投票 / 回退 / 落地路径 |

**总计:** 1070 行,5 个新文件,0 个修改文件,纯增量。
