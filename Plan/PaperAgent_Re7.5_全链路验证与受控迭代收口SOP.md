# PaperAgent Re7.5：全链路验证与受控迭代收口 SOP

> 定位：本 SOP 不新增产品功能。它在 Re6.0--Re6.6、Re7.1--Re7.4 的实现完成后执行，
> 用长回归、盲测、故障注入和受控修复把“局部跑通”变成“可证明的工程结论”。  
> 预计：8--12 个有效工作日，最多 3 轮受控迭代。  
> 终态：形成可用于 Demo、面试和 Beta 决策的 release evidence package，而不是一份口头“测试通过”。

## 目录

1. 前置条件与禁止项
2. 总体闭环
3. 测试资产与分层
4. 三轮迭代流程
5. 失败归因与修复菜单
6. 验收门槛与 No-go
7. 产物、报告与交接

## 1. 前置条件与禁止项

只有以下产物已存在或明确标为未完成时，才进入 Re7.5：

- Re6：Provider/Router、性能修复、学术裁缝、鲁棒性、RAG 上线前收口；
- Re7.1：任务队列、取消、恢复、缓存、预算；
- Re7.2：10 个跨域 fixture；
- Re7.3：引用可追溯、版权/保留策略、无证据拒答 MVP；
- Re7.4：反馈记录与离线聚合 MVP。

本期禁止：

- 为了让 fixture 通过而删除风险提示、降证据门槛或硬编码题目答案；
- 根据单个模型/单个网络波动修改全局 prompt；
- 把用户反馈直接写回 prompt、RAG index 或模型上下文；
- 用 skipped 测试、手工截图或“本机曾跑过”代替可复现证据；
- 在没有失败分类前同时改 prompt、router、检索和 schema。

## 2. 总体闭环

```text
冻结版本与配置
  -> 分层测试 + 全量 replay + 故障注入
  -> 汇总失败（按 failure signature，不按节点名称）
  -> 选择一个可证伪修复假设
  -> 小范围目标回归
  -> 全量回归 + 未见盲测
  -> PASS / HOLD / NO-GO
```

每一次改动必须有一条 `ChangeHypothesis`：

```json
{
  "failure_signature": "empty_expansion_reverify",
  "hypothesis": "expanded_papers 为空时误回退验证旧候选",
  "change_scope": ["citation_expander", "graph_route"],
  "expected_gain": "减少一次 verify，不改变既有 accepted 集",
  "must_not_regress": ["新增 expanded paper 必须验证", "accepted 不可丢失"],
  "target_tests": ["RAG-ROUTE-03", "XD-01", "XD-06"]
}
```

无此记录的代码或 prompt 修改不得进入下一轮全量测试。

## 3. 测试资产与分层

| 层级 | 内容 | 何时运行 | 合格证据 |
|---|---|---|---|
| L0 静态合同 | schema、状态机、secret redaction、SSRF、citation/binding、job transition | 每次改动 | 全绿，P0 0 fail |
| L1 emulator | provider 返回 malformed JSON、429、timeout、错误 tool result、worker crash | 每次改动相关模块 | fallback/partial/cancel 合同正确 |
| L2 定向 replay | 3 个代表题：高证据、弱证据、高风险 | 每次修复后 | target failure 消失且不回归 |
| L3 固定全量 | Re7.2 的 10 个跨域题 × 主模型；关键题 × fallback 模型 | 每一轮收口 | 质量/性能/成本对比 |
| L4 未见盲测 | 5 个不参与设计的题目 | 每轮全量后 | 不允许只在 fixture 上变好 |
| L5 真实 smoke | 3 个 live 题，外部源状态记录 | 最终轮 | API 波动可解释、不伪造成功 |
| L6 UX/人工复核 | RAG 引用、创新点、反馈、取消恢复 | 最终轮 | 可操作、可理解、可追溯 |

运行超过 60 秒且相互独立的 case 必须并行分配；主执行者同时整理失败分类、准备人工 rubric 和
下一轮 target tests。并发上限以 provider 的 429/排队实测值为准，默认不超过 2 个 LLM run。

## 4. 三轮迭代流程

### Round 0：冻结基线（1 天）

1. 固定 commit、环境依赖、fixture 版本、source policy、provider/model、prompt/contract 版本；
2. 清点已有 worktree 噪声，将生成 artifact 写入独立 `artifacts/re7_5/<baseline_id>/`；
3. 跑 L0/L1、10 题主模型 replay、关键 3 题 fallback、5 个故障注入；
4. 输出基线表：质量、p50/p95、LLM call 数、预算耗尽、fallback、RAG abstain、取消恢复结果。

这一轮不得修复。它只回答“现在真实表现怎样”。

### Round 1：确定性/P0 修复（2--3 天）

只处理以下问题：安全、数据丢失、错误成功、无限循环、无证据强回答、取消后继续调用、原始 key 泄露。

- 每个 failure signature 最多一个最小修复；
- 先跑 L0/L1 + 对应 3 个 replay；通过后再跑 L3；
- 若修复使任一 P0 变差，立刻回滚该修复，不与其他修复捆绑；
- 每个修复产出 before/after diff，不凭主观“回答更好”合入。

### Round 2：质量、跨域与性能修复（3--4 天）

按优先级处理：跨域 verdict 错判 > 证据缺失 > fallback 漂移 > 关键路径耗时 > 文字风格。

可选策略只允许灰度对比：

- `repair/promote/hybrid` 检索门控；
- 分析链真实并行与 bundle synthesis；
- 不同模型 generator/reviewer 角色绑定；
- RAG 检索阈值、citation validator 与 abstain policy。

每项策略必须在 10 fixture + 5 holdout 上比较，且不允许只报告均值：同时报告最差 case、成本与
quality regression。跨域结果由双人 rubric 判定，无法判定时记录 `ambiguous`，不强行算 pass。

### Round 3：Beta 演练与最终盲测（2--4 天）

1. 5 个未见题盲测，执行者不能为这些题改 prompt 或 fixture；
2. Job cancel/resume/cache/budget 组合故障注入；
3. RAG 上传/删除/无证据/伪造 citation/版权声明的端到端测试；
4. 10 条模拟用户反馈，验证关联、幂等、聚合与“不进入 LLM”；
5. 演练一场 5 分钟 Demo：成功案例、PIVOT 案例、STOP 案例、可解释 fallback；
6. 召开 release review，只允许 `PASS|HOLD|NO_GO` 三种结论。

## 5. 失败归因与修复菜单

| Failure signature | 首选排查 | 可尝试修复 | 不允许的修复 |
|---|---|---|---|
| JSON/字段漂移 | ResponseEnvelope、node contract、repair trace | node-specific validator、一次有界 repair、typed fallback | 通用 verifier formatter 污染所有节点 |
| 空 repair/重复检索 | query IDs、repair outcome、gate route | 确定性 query、空计划终止、weak policy A/B | 再加一次盲目 LLM repair |
| 跨域错判 | raw_topic、atoms、evidence/risk rubric | domain skill atom、hard guard、要求缺失证据 | 给某题硬编码关键词 |
| 创新点华而不实 | P-M-I、BaselineCard、CompatibilityMatrix | Re6.4.1 gate、falsifier、对照实验 | 改写得更夸张或隐藏 limitation |
| RAG 强答无证据 | retrieved/cited 集合、score、citation locator | server-side citation validation、abstain、extractive fallback 标识 | 相信模型 confidence |
| 长任务卡死/超支 | job state、lease、event、provider timeline | cooperative cancel、checkpoint、budget guard、cache | kill 进程后标 succeeded |
| 反馈污染 | feedback storage、prompt trace | append-only、人工聚合、脱敏 | 直接把评论塞回 agent |
| 性能无改善 | wall-clock timeline、provider queue、call count | 去空跑、批处理/并行实验、降级模式 | ToT 增加多轮调用 |

同一种 failure signature 连续三轮仍无法改善时，停止微调，提交 ADR：保留、替换或删除该能力，
并注明用户价值、成本、风险和替代方案。

## 6. 验收门槛与 No-go

### P0：必须 100% 通过

- 无 raw API key、私密正文或未脱敏 URL 写入日志/trace/前端；
- SSRF、非法重定向、取消后继续执行、错误标成功、无限 repair 均为 0；
- 非拒答 RAG 回答的 citation 均能定位到本轮检索 evidence；无证据强回答为 0；
- 创新点的核心主张均标明证据或 `needs_evidence`，未跑实验不得写成已证实；
- job 的 cancel/resume/budget 状态转换和 artifact 完整性全绿；
- 用户反馈不进入 LLM 上下文。

### P1：目标门槛

| 指标 | 门槛 |
|---|---:|
| 10 跨域题人工 verdict 一致 | >= 8/10 |
| 5 未见题不低于固定集 | >= 4/5 不发生严重错判 |
| RAG citation validity | 100% |
| RAG 无关问题正确拒答 | >= 19/20 |
| Innovation P-M-I/evidence 合同 | >= 85% |
| fallback 失败显式可见 | 100% |
| 相对 Round 0 中位端到端耗时 | 降低 >= 25% 或给出不可降低的 provider 证据 |
| 单 run 预算耗尽后仍可读 partial | 100% |

`NO_GO`：任一 P0 失败；或 P1 连续两轮未达标且 holdout 无改善；或 Demo 只能展示成功样例、
无法解释 PIVOT/STOP/失败。

`HOLD`：P0 通过、P1 部分未达标；允许作为本地作品集，但不得开放 Beta 真实用户。

`PASS`：P0 全绿、P1 达标、已完成盲测与 release review；可进入受限 Web Beta。

## 7. 产物、报告与交接

每一轮必须保存：

```text
artifacts/re7_5/<round>-<run_id>/
  manifest.json                 # commit/config/fixture/provider versions
  metrics.json                  # latency/cost/quality/fallback
  failure_taxonomy.json
  provider_timeline.json
  cross_domain_rubric.csv
  rag_trust_report.json
  job_runtime_report.json
  feedback_isolation_report.json
  change_hypotheses.json
  decision.md                   # PASS/HOLD/NO_GO + next action
```

最终报告必须包含：

1. Round 0 与最终轮的表格对比；
2. 每个未通过项、已知限制与下一步 owner；
3. 三个可面试讲述的工程复盘：模型输出漂移、长任务治理、证据拒答；
4. Demo 脚本、公开案例边界和 Beta 是否允许的结论。

执行者交接时只需读取 `decision.md + failure_taxonomy.json + change_hypotheses.json`，
不得从旧日志中猜测下一步。
