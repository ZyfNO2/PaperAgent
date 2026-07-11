# PaperAgent Re6.X：多模型与学术裁缝鲁棒性路线图

> 制定日期：2026-07-11  
> 承接：Re4.0 工程化收口与 Re5.X 检索反思迁移性升级。  
> 周期建议：约 26 个有效开发日，以阶段门推进。  
> 终局目标：安全接入用户自有模型；不同模型输出不破坏 Agent 合同；创新点具备
> 证据、可证伪性和独立审查；阶段结束时有跨模型、跨域、RAG 前置与未来上线的
> 可复验证据。

---

## 1. Re6.X 要解决的真实问题

当前工作区已有 provider registry 与管理 API，但它和生产 llm_router 仍是两套
平行机制：前端没有设置页；registry 的切换不保证影响生产 call_json；通用 JSON
formatter 含 verifier 专用字段；formatter 缺 repair depth；用户自定义 URL/key
没有完整的 SSRF、密钥与协议能力边界。

Re4.3 已加入创新点 evidence IDs 与 binding validator，但尚缺：

- Problem–Method–Insight 三层主张；
- 伪创新识别和相邻工作差异矩阵；
- 可证伪命题、支持/反驳条件和实验计划；
- 独立 reviewer pressure test；
- 创新点的版本演化与用户批准机制。

中心判断：

> 模型切换不是下拉框，而是安全、能力协商、结构化输出合同、fallback 与 run
> snapshot 组成的控制面。学术裁缝不是一条 prompt，而是证据约束下的生成、
> 审查、证伪和演化闭环。

---

## 2. 终态范围

| 能力 | Re6.X 交付 | 不做 |
|---|---|---|
| 用户模型配置 | URL、key、协议、模型发现、连接 probe、角色绑定、fallback 顺序 | 公网多租户密钥托管、计费、团队共享 vault |
| 模型路由 | 每个 task role 独立 primary/fallback/contract | 一个全局模型控制所有节点 |
| 输出兼容 | provider envelope、节点专属 schema、语义校验、一次修复 | 通用正则或 verifier 专用修复 prompt 处理所有节点 |
| 创新点 | 三层主张、伪创新审查、可证伪命题、演化日志 | 无文献证据时的 first claim 或自动定稿 |
| RAG 前置 | 引用/chunk binding、无证据拒答、模型与 retrieval 解耦 | 重做 Re5 的全文 RAG 管道 |
| 上线准备 | 密钥、SSRF、审计、删除和运行快照的设计与验证 | 公网发布、账号、支付 |

---

## 3. Paper-novelty-design Skill 的正式接入

参考项目：[LaVineLeo/Paper-novelty-design](https://github.com/LaVineLeo/Paper-novelty-design)，
审阅基准 commit：9434234aa44d303102a6619cbb91e7ab7a92869a，许可证 MIT。

本项目采用其五类方法论：

1. Problem–Method–Insight 三层表达；
2. 缺 motivation、工程堆料、跨域移植、指标叙事、脆弱 first claim 五类伪创新陷阱；
3. support、refute、required test 三要素的可证伪命题；
4. repetition、motivation、falsifiability、differentiation、story 五类压力测试；
5. innovation evolution log。

### 3.1 接入方式与许可

| 层 | Re6.X 处理 |
|---|---|
| 方法论与 prompt | 可按 MIT 复用；复制原文/文件前，写入 THIRD_PARTY_NOTICES.md 并保留版权与 MIT 文本 |
| 数据结构 | 重定义为 PaperAgent Pydantic schema，所有主张绑定 candidate/chunk evidence IDs |
| 运行时 | 新增 NoveltyReviewAdapter；不依赖外部 skill 进程 |
| 文献真实性 | 仍由 retrieval、verifier、RAG evidence 负责；NoveltyReviewAdapter 不得生成或验证文献事实 |
| first claim | 固定标记 requires_literature_verification，除非存在已审查的相邻工作差异矩阵 |

### 3.2 不可跨越的规则

- 指标提升是 evidence，不是 Insight；
- 无可定位 evidence 时，输出 needs_evidence，不是创新结论；
- 同一模型生成与审查时必须标记 self-review；
- 正式模式优先使用不同模型作为 reviewer；
- 用户决定是否接受或应用主张改写，系统只返回 proposal。

---

## 4. 目标架构

~~~mermaid
flowchart TB
    U["用户设置页"] --> W["Provider Wizard"]
    W --> V["Validate / Discover / Capability Probe"]
    V --> S["Session-only 或 Local Vault"]
    S --> R["Model Policy Registry"]

    R --> A["Task-role Router"]
    A --> C["Structured Output Contract"]
    C --> P["Provider Adapter"]
    P --> N["Response Envelope Normalize"]
    N --> Q{"Schema + semantic validation"}
    Q -->|pass| T["Node result + provenance"]
    Q -->|repairable| F["One bounded repair"]
    F --> Q
    Q -->|retryable| A
    Q -->|terminal| X["Typed failure / explicit heuristic"]

    T --> EC["Evidence Context Compiler"]
    EC --> NG["Novelty Draft Generator"]
    NG --> NV["NoveltyReviewAdapter"]
    NV --> FP["Falsifiability Planner"]
    FP --> CJ["Claim Judge + Binding Validator"]
    CJ --> EL["Novelty Evolution Log"]
    EL --> UI["Innovation Workbench"]
~~~

### 4.1 不变原则

1. 每个 run 固定 model policy snapshot；中途切换不改写历史结果。
2. 每次 fallback 写入角色、provider、model、错误分类、合同版本、是否 heuristic。
3. 结构化输出先过合同，后进入业务。
4. 学术主张先过 evidence binding，后写入报告。

---

## 5. 多模型控制面

### 5.1 按任务角色路由

| Task role | 典型节点 | 首要能力 | 策略 |
|---|---|---|---|
| structured_extract | topic parser、verifier、dataset extractor | 稳定 JSON | 严格 schema，可切 formatter |
| search_control | planner、SearchController、repair | 指令遵循、短 JSON | 低温、预算受控 |
| evidence_critic | low-bar、devils advocate、novelty review | 反方推理、证据约束 | 要求 evidence IDs |
| novelty_draft | innovation extractor、贡献写作 | 研究表达 | 不允许 first claim |
| narrative_write | narrative/report phrasing | 可读性、一致性 | 不承担事实判定 |
| rag_answer | RAG QA | 引用忠实、拒答 | 无 cited chunks 则代码拒答 |
| formatter | JSON repair | 格式服从 | 单次、无业务判断 |

ModelPolicy 示例：

~~~json
{
  "role": "novelty_draft",
  "primary": {"provider_id": "provider-a", "model_id": "model-a"},
  "fallbacks": [{"provider_id": "provider-b", "model_id": "model-b"}],
  "contract_version": "novelty-candidate/v1",
  "temperature": 0.2,
  "allow_heuristic": false,
  "max_provider_attempts": 2,
  "max_format_repairs": 1
}
~~~

### 5.2 ProviderProfile 与 API key

ProviderProfile 最少包含 provider_id、label、protocol、base_url、secret_ref、
selected models、capabilities、status、config_version。

密钥规则：

- 默认 session-only；浏览器关闭/显式删除后不可恢复；
- key 不进入 URL、query string、localStorage、trace、日志、错误正文或截图；
- Save to local vault 才允许持久化；本地使用 OS keyring 或加密文件，主密钥不入仓库；
- GET API 只返回 api_key_set 和 secret_ref 类型；
- 删除 profile 时删除 secret，ledger 仅保留无密钥 tombstone。

### 5.3 自定义 URL 与 SSRF

- 仅接受 http/https，默认只接受 https；
- DNS 后拒绝 loopback、private、link-local、metadata IP 和重定向到内网；
- localhost/Ollama 仅在 explicit local_mode 下允许，并在 UI 明示；
- 限制端口、跳转、超时、响应大小、并发；
- models discovery 与 chat probe 共用 URL 安全层；
- 原始错误正文截断并 redaction。

### 5.4 模型发现与能力探测

Provider Wizard：

1. 输入 label、protocol、URL、key；
2. 后端在短生命周期 session 中验证 URL/key；
3. OpenAI-compatible 协议尝试 models endpoint；
4. models endpoint 不支持时允许手工填 model，并显示 discovery unsupported；
5. 对选定 model 探测 chat、JSON object、JSON schema、reasoning envelope、streaming；
6. 用户绑定 task roles 和 fallback；
7. Save 后生成 config_version；新 run 才使用新 snapshot。

能列出 models 不代表模型可用，必须通过 selected-model probe。

---

## 6. 不同模型输出的兼容层

### 6.1 ResponseEnvelope

Provider adapter 必须先归一化：

~~~json
{
  "provider_id": "...",
  "model_id": "...",
  "request_id": "...",
  "content": "...",
  "reasoning": "...",
  "tool_calls": [],
  "finish_reason": "...",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "raw_shape": "openai_chat|anthropic_message|custom"
}
~~~

业务节点只读取此 envelope，不直接解析厂商响应。

### 6.2 StructuredOutputContract

每个 structured role 注册：

~~~json
{
  "contract_id": "novelty-candidate/v1",
  "json_schema": {},
  "semantic_validator": "validate_novelty_candidate",
  "accepted_envelopes": ["content_json", "reasoning_json"],
  "repair_strategy": "same_model_once|formatter_once|fallback_model_once|fail",
  "max_repairs": 1,
  "fallback_behavior": "typed_failure|heuristic_marked"
}
~~~

通用 formatter 必须接收该节点的真实 schema，不能再写 verifier 专属字段。
repair_depth 超过 1 时返回 typed failure，禁止递归 formatter。

### 6.3 错误分类

| 分类 | 例子 | 行为 |
|---|---|---|
| invalid_auth | 401、无效 key | 不重试，标 profile invalid |
| permission_denied | 403、无模型权限 | 提示换 model |
| model_not_found | 404 model | 刷新 discovery 或手填 |
| rate_limited | 429 | 有界退避或切 fallback |
| transient_network | timeout、5xx | 有界 retry 后切 fallback |
| context_too_large | token/context 超限 | 先压缩 context，不可静默截证据 |
| malformed_output | 无 JSON、schema fail | 一次 format repair，再切 fallback |
| semantic_contract_fail | ID 不存在、引用不支持 | 返回任务模型一次带 validator feedback |
| unsupported_protocol | 非预期响应形状 | 停止 onboarding |

所有降级在 UI 和 trace 中显示最终 provider/model、错误类型、质量等级变化。

---

## 7. 前端设计

新增 Settings / Models 页面：

1. Provider Profiles：协议、健康、模型数、secret 状态；
2. Add Provider Wizard：URL/key/protocol → discover → probe → role binding → save；
3. Role Routing Matrix：primary、fallback、temperature、heuristic policy；
4. Run Snapshot Viewer：每个 case 的 provider/model/contract/fallback；
5. Security Notice：保存位置、local mode、删除入口、日志保护。

体验规则：

- key 输入后立即从前端 state 清空，不回显；
- discovery 失败不能误导为连接失败；
- probe 按能力逐项展示；
- 模型切换只影响新 run；
- heuristic 或 reviewer independence degraded 必须在报告中显著标注。

---

## 8. 学术裁缝 2.0

### 8.1 数据链路

~~~mermaid
flowchart LR
    A["Verified papers + RAG chunks"] --> B["Evidence Context Compiler"]
    B --> C["Adjacent-work Differentiation Matrix"]
    C --> D["Novelty Draft Generator"]
    D --> E["Binding Validator"]
    E --> F["NoveltyReviewAdapter"]
    F --> G["Falsifiability Planner"]
    G --> H["Claim Judge"]
    H --> I["Novelty Evolution Log"]
    I --> J["User accept / revise"]
~~~

新增 schema：

| Schema | 关键字段 |
|---|---|
| EvidenceContext | candidate_id、chunk_id、snippet、location、role、source quality |
| NoveltyCandidate | problem、method、insight、scope、candidate_ids、chunk_ids、status |
| DifferentiationMatrix | adjacent_work、Problem/Method/detail/evidence/Insight 五层差异 |
| FalsifiableProposition | proposition、support、refute、required_test、evidence_ids |
| ReviewerPressurePoint | risk、question、severity、repair、evidence_ids |
| ContributionProofPlan | contribution、evidence_needed、weakest_link、threshold |
| NoveltyRevision | version、parent、reason、evidence_delta、next_falsification_test |

ID 不存在、snippet 无定位、Insight 只有指标改善时，状态只能是 needs_evidence 或
needs_rewrite。

### 8.2 Prompt A：证据约束的创新草案

~~~text
你是受证据约束的研究贡献设计者。只根据 EVIDENCE_CONTEXT 和 ADJACENT_WORKS
生成候选主张；不能发明文献、结果、机制或首次结论。

每个候选必须包含：
1. Problem：具体且有边界的未解决缺口；
2. Method：直接针对该缺口的具体干预；
3. Insight：忘掉模型名称后仍可复用的条件性发现；
4. scope：适用任务、数据条件和不适用边界；
5. evidence IDs：Problem、Method、Insight 各至少一个。

性能提升只能作为 evidence，不能单独作为 Insight。
无法形成 Insight 时输出 needs_evidence，不可包装模块拼接为创新。
返回 NoveltyCandidate JSON 数组。
~~~

### 8.3 Prompt B：NoveltyReviewAdapter

~~~text
你是匿名审稿人。对 NOVELTY_CANDIDATE 执行 repetition、motivation、
falsifiability、differentiation、story 五项测试。

检查：
- Problem 是否具体且有证据；
- Method 是否真的解决 Problem，而非工程堆料；
- Insight 是否独立于指标提升；
- 跨域移植是否解释直接复制为何失败、做了什么适配、得到什么可迁移认识；
- first claim 是否标为待文献验证；
- 每条批评必须引用 evidence_id，缺证据时写 unknown。

返回 verdict、pseudo_innovation_risks、pressure_points、
differentiation_matrix、required_repairs。
~~~

### 8.4 Prompt C：可证伪命题规划

~~~text
只把已通过 binding 的 Insight 转化为 1 至 3 条可证伪命题。

每条命题必须包含 scoped setting、observable effect、support condition、
refute condition、required test 和 evidence IDs。
若现有资源无法执行 required test，标为 planned_not_verified，
不得写成已被证明。
~~~

### 8.5 模式

| 模式 | Generator | Reviewer | 适用 |
|---|---|---|---|
| Conservative | 同模型、低温 | 同模型，标 self-review | 本地快速迭代 |
| Cross-model | 写作模型 | 不同 critic model | 正式开题、投稿前 |
| Human-led | 系统生成问题/矩阵 | 用户判断，模型只改写 | 证据不足或高风险 |

---

## 9. 长程任务表

| 阶段 | 有效工作日 | 任务 | 交付物 | 阶段门 |
|---|---:|---|---|---|
| R6-0 基线冻结 | 2 | 冻结 provider/router、Re5 检索、prompt 与测试基线；ADR | baseline report、风险清单 | 未冻结不得调 prompt |
| R6-1 Provider Core | 4 | URL safety、ProviderProfile、SecretStore、协议 adapter、discover/probe | provider API v2、typed errors、ledger | 无 raw key 泄露 |
| R6-2 Router Unification | 4 | role ModelPolicy、ResponseEnvelope、OutputContract、有界 repair | 单一 router、run snapshot | registry 切换真实影响新 run |
| R6-3 React Settings | 3 | Wizard、role matrix、snapshot viewer、删除/会话提示 | Settings 页面、Playwright | 浏览器无 raw key |
| R6-4 Academic Tailor 2.0 | 5 | context compiler、review adapter、命题/日志、UI | schema、validators、review report | 无证据/first claim 不可通过 |
| R6-5 Robustness Lab | 5 | emulator、replay、hidden 跨域集、fallback chaos tests | evaluation harness、对比报告 | 满足验收文档 P0/P1 |
| R6-6 RAG/上线前收口 | 3 | RAG 合同、SSRF/secret/observability 审查、Runbook | readiness package | 无阻塞项才可规划上线 |

总计约 26 个有效开发日。R6-1 或 R6-2 的安全/合同门失败时，暂停 UI 和学术裁缝，
优先修底座。

---

## 10. RAG 与未来上线前置保证

- RAG retrieval 与 model generation 解耦；模型变化不改变页码/chunk IDs；
- RAG answer 无 cited_chunks 时由代码拒答或返回不确定；
- RAG context 是不可信数据，不能覆盖 system instruction；
- provider、PDF、网页 URL 分别走 SSRF policy；
- trace 保存 hash、schema/error/fallback 元信息，不保存 key 或完整私密原文；
- 上线前补账号边界、per-user secret isolation、HTTPS、CSRF/CORS、rate limit、
  删除与导出策略；
- 本地、单用户、服务端模式必须在 UI 和 Runbook 中明确区分。

---

## 11. 本期完成标准

- [ ] 用户可完成 URL/key/protocol/model 的 validate、discover、probe 与 role binding。
- [ ] provider registry 和生产 router 已统一；新 run 有不可变 snapshot。
- [ ] 所有 structured node 使用节点专属输出合同；formatter 无递归和字段污染。
- [ ] fallback 可解释；不可恢复错误不静默变成功。
- [ ] NoveltyReviewAdapter 已实现三层主张、伪创新、可证伪、演化日志方法。
- [ ] 创新点均有 evidence binding；无证据/first claim 不能包装为已证实。
- [ ] 跨模型、跨域、fallback、RAG、密钥与 URL 安全验收通过。
- [ ] 测试证据、模型版本、prompt hash、fixture hash 和已知限制已归档。

