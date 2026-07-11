# PaperAgent Re6.X：鲁棒性、跨域、RAG 与上线前验收规范

> 适用范围：Re6.X 多模型控制面、学术裁缝 2.0，以及 Re5 检索反思和 Re4 RAG 的回归保护。  
> Release 条件：所有 P0 必须通过；P1 达标；P2 有 owner 与风险登记。

## 1. 验收对象

| 对象 | 必须证明 | 不可接受的替代证据 |
|---|---|---|
| Provider onboarding | URL、key、协议、模型能安全验证、发现或手工配置 | 只看 HTTP 200 或模型列表 |
| Model router | 新 run 实际使用选择的 role policy | registry 值变化但 production router 未消费 |
| Structured output | 不同模型通过正确节点合同或显式失败 | 从文本抠出 JSON 就视为成功 |
| Fallback | 错误分类、次数、质量降级可解释 | catch all 后静默 heuristic |
| Novelty tailor | 主张有 evidence、可证伪、可被 reviewer challenge | 语言流畅或模型自评 accept |
| Cross-domain | 未见领域和异常条件下保持合同和合理降级 | 只跑已有回归题库 |
| RAG | 引用支持回答，模型变化不改检索证据 | 只显示论文标题 |
| 上线安全 | key、URL、日志、权限、删除有边界 | 本机能跑即可 |

每项产物必须有：code hash、provider config version、model ID、prompt hash、
contract version、fixture hash、run ID、环境、耗时与结论。记录不得含 key 或完整私密原文。

## 2. 测试分层

~~~mermaid
flowchart TB
    A["L0 静态合同 / 安全单测"] --> B["L1 Provider emulator 集成"]
    B --> C["L2 固定 replay 端到端"]
    C --> D["L3 跨模型 / 跨域 hidden 盲测"]
    D --> E["L4 小规模 live smoke"]
    E --> F["L5 RAG + 上线前 readiness review"]
~~~

### L0：静态合同与安全单测

- ProviderProfile、ModelPolicy、ResponseEnvelope、StructuredOutputContract schema；
- key redaction；API、日志、异常、trace 均无 raw key；
- URL scheme、DNS/IP、redirect、port、local_mode 的 SSRF 规则；
- models discovery 的 success、unsupported、401、404、malformed；
- fallback chain 去重、无循环、最大尝试次数；
- formatter 的 repair_depth 最大为 1；
- SearchCard、query ledger、Coverage Gate 回归；
- NoveltyCandidate、FalsifiableProposition、EvolutionLog 的 evidence ID 完整性；
- RAG answer 的 cited_chunks 缺失拒答。

**P0：L0 必须 100% 全绿。**

### L1：Provider emulator 集成

| Emulator | 响应形态 | 预期 |
|---|---|---|
| openai-json | 标准 chat + content JSON | 直接通过 |
| reasoning-json | reasoning 有 JSON，content 有 prose | envelope 解析后通过 |
| markdown-json | fence 包 JSON | 一次 parse 后通过 |
| malformed-once | 首次缺字段，repair 后合法 | 一次 repair 后通过 |
| malformed-always | 始终不合 schema | 有界失败/切 fallback，不递归 |
| auth-429-5xx | 401、429、503 | 分类、退避/切换符合 policy |
| models-unsupported | GET models 为 404/405 | UI 允许手工 model |
| anthropic-like | messages/content blocks | adapter 正确归一化 |

**P0：最终 provider/model、error class、fallback attempts 与 trace 断言完全一致。**

### L2：固定 replay 端到端

冻结 retrieval、RAG、provider emulator fixture，比较 control 与候选策略：

- Re5 SearchController 的 template control 与 A/B/C prompts；
- 每个 task role 的 primary/fallback；
- 创新点的充分证据、薄弱证据、重叠相邻工作、跨域移植、指标故事；
- RAG 的强证据、冲突证据、无命中、扫描 PDF、上下文注入文本；
- 前端 onboarding → probe → role bind → new run → snapshot → fallback visible。

同一 fixture、预算和 prompt hash 下运行；每次只改变一个变量。

### L3：跨模型与跨域 hidden 盲测

Prompt、schema、router policy 和阈值在 hidden 解封前冻结。执行者不能根据 hidden 失败逐题调 prompt。

### L4：Live smoke

- 每 provider 最多两次低 token probe；
- source 限并发和成本；
- 只判断 success/degraded/typed failure；
- 外网偶然成功不能覆盖 L2/L3 的失败。

### L5：Readiness review

独立 reviewer 检查测试报告、trace redaction、URL 防护、RAG 引用、密钥删除和已知限制，输出 release/no-go。

## 3. 跨域与模型矩阵

| 集合 | 数量 | 内容 | 用途 |
|---|---:|---|---|
| Dev | 24 | 已知领域均衡样本 | 调 prompt、修 schema |
| Hidden-OOD | 48 | 未见领域、对象、术语组合 | 选择最终策略 |
| Failure | 16 | 无结果、429、鉴权、模型不存在、超长 context、空 PDF | 错误与降级 |
| Novelty gold | 24 | 五类创新质量案例 | 学术裁缝 |
| RAG gold | 30 问题 | 10 个文档版本、人工页码/段落 | 引用与拒答 |

Hidden-OOD 至少覆盖：医学、土木、遥感、工业制造、机器人、材料、能源、CV、NLP、时序、图学习、无 repo、无数据集、中文长题、英文缩写、跨域组合和不可行冷门题。

模型按能力原型测试：

| 原型 | 重点风险 |
|---|---|
| Strict JSON model | 合同直通、低成本角色 |
| Reasoning model | reasoning/content 分离 |
| Markdown-first model | prose/fence 输出 |
| Weak instruction model | 缺字段、枚举漂移 |
| OpenAI-compatible endpoint | discovery、URL、协议 |
| Anthropic-like endpoint | messages/content blocks |

每个原型至少由一个 emulator 和一个授权 live provider 覆盖。

## 4. 多模型输出与 fallback 验收

| 指标 | 定义 | 门槛 |
|---|---|---|
| Direct schema pass | 首次输出通过 schema | 按模型报告 |
| Repaired schema pass | 一次 repair 后通过 | 不得掩盖 semantic fail |
| Semantic contract pass | IDs、枚举、evidence、业务不变量通过 | P0：100% 或 typed failure |
| Silent degradation | 不合格输出仍被业务消费 | P0：0% |
| Repair recursion | repair depth 超限/循环 | P0：0% |
| Attribution completeness | trace 有 provider/model/contract/fallback | P0：100% |

| 注入故障 | 期望 | 禁止 |
|---|---|---|
| 401 | invalid_auth，停止 profile | 换模型后仍使用坏 key |
| 403 | permission_denied，提示无权 | 伪装 network error |
| model 404 | model_not_found，允许重选 | 自动猜模型名 |
| 429 | 有界退避或切 fallback | 无限 sleep |
| 5xx/timeout | 有界 retry 后 fallback | 无预算重试 |
| JSON 缺字段 | 单次 node-specific repair | verifier 字段污染其他节点 |
| semantic fail | validator feedback 或 typed failure | formatter 伪造 ID |
| context too large | 压缩并记录 evidence loss | 静默截断引用 |
| 全 fallback 失败 | typed failure 或 heuristic_marked | success + 空对象 |

Provider onboarding P0：

- [ ] key 不在 React snapshot、response、server log、trace、screenshot、Git；
- [ ] URL/private-IP/redirect SSRF 测试全绿；
- [ ] models endpoint 404/405 时可手工填 model；
- [ ] 手工 model 必须通过 chat/JSON probe；
- [ ] 删除 profile 同时删除 secret；
- [ ] switch 只影响新 run；历史 run 保留 snapshot 但不可恢复 key；
- [ ] registry 选择与 production call_json 的实际 provider 一致。

## 5. 学术裁缝验收

| Novelty gold 类型 | 正确系统行为 |
|---|---|
| 强候选 | 有边界的 Problem–Method–Insight 与命题 |
| 工程堆料 | mostly_engineering 或 needs_motivation |
| 跨域移植 | 说明直接复制失败点、适配和可迁移认识 |
| 相邻工作重叠 | too_close 或 needs_literature_verification |
| 证据薄弱 | needs_evidence，不生成强贡献 |
| first claim | requires_literature_verification |
| 反例出现 | 缩小 claim，写入 evolution log |
| 指标故事 | 性能只作为 evidence，不作为 Insight |

创新点 P0：

- [ ] Problem、Method、Insight 都绑定可解析 evidence ID；
- [ ] Insight 不是纯性能/模型名陈述；
- [ ] first claim 降级；
- [ ] 命题有 support、refute、required test；
- [ ] 不可执行 test 为 planned_not_verified；
- [ ] reviewer point 有 target 与 evidence 或 unknown；
- [ ] evolution log 不覆盖历史；
- [ ] 用户未 accept 的 proposal 不进入最终报告。

创新点 P1：

| 指标 | 门槛 |
|---|---|
| P-M-I 完整且逻辑连通 | 至少 85% |
| 伪创新风险召回 | 至少 80% |
| 无证据强 claim 误放行 | 0% |
| first claim 正确降级 | 100% |
| 可证伪命题可执行率 | 至少 85% |
| 相邻工作重叠识别 | 比 control 高至少 10 个百分点 |
| reviewer independence 标注 | 100% |

人工 disagreement 必须保存，不能以模型分数覆盖。

## 6. 检索、RAG 与模型切换联合验收

检索不变量：

- 模型变化不改变 SourcePolicy、query ledger、Coverage Gate 和 source status；
- allowed sources 来自 runtime catalog；
- empty、failed、rate_limited、disabled 语义独立；
- query 有 fingerprint、target role、证据来源；
- required role 未满足时不能因论文数足够 stop。

RAG 不变量：

| 场景 | 期望 |
|---|---|
| 模型不同，检索相同 | cited chunks、页码、ranking 在同一 index 不变 |
| 模型无引用 | API abstain 或 typed citation failure |
| 证据冲突 | 陈述冲突，不选边编造 |
| 无命中 | 返回不确定与建议 |
| PDF 文本含指令 | 不可信文本，不能改变 system/工具策略 |
| context 超限 | 记录压缩/截断 chunk IDs 与影响 |
| provider 故障 | retrieval 可返回；generation 为 degraded/failed |

RAG gold 首轮门槛：citation validity 100%；no-answer precision 至少 90%；supporting chunk recall at 5 至少 80%；模型切换后 citation validity 不下降；无证据强回答为 0。

## 7. 上线前安全与运维门

P0：

- [ ] 无 raw API key 日志、trace、响应、浏览器持久化或 Git tracked 文件；
- [ ] 自定义 URL SSRF 拒绝；
- [ ] profile/secret 可删除和失效；
- [ ] 区分只读、配置写、运行写、删除写权限；
- [ ] CORS、CSRF、HTTPS、session boundary 有 ADR；
- [ ] 上传、PDF 抽取、网页抓取、provider probe 各有限制和审计；
- [ ] 未认证公网模式不能启用 local_mode/private URL；
- [ ] error redaction 全绿。

P1：

- [ ] provider 有 timeout、并发、retry 和 circuit breaker；
- [ ] run 有 provider/model/prompt/contract/fallback；
- [ ] metrics 包含 provider error、fallback、schema fail、citation failure、RAG abstain、source 429；
- [ ] Runbook 包含无 key、坏 key、模型下线、context 超限、RAG 无证据、SSRF 拒绝；
- [ ] Known Limitations 按 local/single-user/server 三种模式写明。

## 8. Release / No-go

Release：

- [ ] L0–L3 通过；L4 仅有允许外网降级；
- [ ] 所有 P0 通过，P1 达标或有批准例外；
- [ ] hidden 对比报告、prompt/provider/fixture/contract 版本齐全；
- [ ] NoveltyReviewAdapter 对伪创新和 first claim 通过 gold；
- [ ] RAG citation validity 100%，无证据强回答为 0；
- [ ] 独立 reviewer 完成安全、日志、删除、Runbook 审查。

No-go：任一条件禁止进入上线设计：

1. 任何位置可读 raw API key；
2. 前端选择和 production router 实际 provider 不一致；
3. formatter 可递归，或把 semantic fail 伪装 schema success；
4. 自定义 URL 可访问私网/metadata；
5. 模型故障后返回未标记 heuristic 或无引用答案；
6. 无证据、first claim、相邻工作重叠仍被创新模块强 accept；
7. hidden 被用于逐题调 prompt 后仍宣称泛化；
8. RAG 无 cited chunks 仍输出确定性结论。

## 9. 试验报告目录

~~~text
artifacts/re6/<run_id>/
  manifest.json
  provider_snapshot.json
  model_policy.json
  prompt_hashes.json
  contract_versions.json
  fixture_hashes.json
  per_case_results.jsonl
  fallback_ledger.jsonl
  security_redaction_report.json
  novelty_review_report.json
  rag_citation_report.json
  aggregate_metrics.md
  failures.md
~~~

缺 manifest、版本快照或失败案例的报告，不得作为鲁棒性已经验证的证据。

