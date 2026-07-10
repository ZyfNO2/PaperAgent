# PaperAgent Re6.1：性能修复快速 SOP

> 制定日期：2026-07-11  
> 输入证据：`tmp_re13_eval/c1f6fd8d76d1/trace_full.json`，端到端 812 s。  
> 目标：先消灭确定无效的 LLM 等待；再用 10 个 case 的对照实验决定检索门控；最后降低分析链的关键路径。不得以删除 evidence binding、低栏审查或失败可见性换取耗时下降。

## 0. 结论与本期边界

此 trace 中可直接认定的浪费有两处：

1. `targeted_repair` 耗时 79.195 s，但 `n_queries=0`；之后仍回到
   `paper_retriever`，没有新的检索意图。
2. `citation_expander` 的 `n_expanded=0`，随后 `verify` 因其空列表回退到
   `paper_candidates`，又花 62.513 s，且将已有 7 篇 accepted 覆盖成空集。

分析链不能把 ToT 当成加速方案：ToT 本质会增加分支和调用数。这里应比较
**真实并行** 与 **有边界的 bundle synthesis**；两者都保留一个独立 reviewer，
不把生成与审查合为同一次“自评”。

## 1. 先补可相信的观测（半天）

现有 `_util.emit_trace()` 在函数返回时才写 `started_at`，因此 trace 中的
`started_at`/`ended_at` 都接近结束时刻，不能用它证明 LangGraph fan-out 是否真的并行。

- [ ] 为每个 node 在入口记录 `wall_started_at`，在 return 前记录 `wall_ended_at`；
      保留 `elapsed_s`。
- [ ] 为每个 LLM 调用记录：`call_id`、node、profile、provider、attempt、
      direct-parse / formatter / validator-repair 阶段、timeout、异常类型；不得记录 key 或原始敏感内容。
- [ ] `dataset_repo` 额外记录：`n_target`、worker 数、每篇 fulltext 耗时、
      每篇 LLM 耗时、成功/空结果/超时/JSON 修复次数。
- [ ] 汇总报表同时计算总墙钟、critical path、LLM call 数、重复 verify 数、
      fallback 比例；不能只相加 node `elapsed_s`。

验收：对同一个 replay，能够判定 `work_package` 与 `sota_matcher` 的调用区间是否重叠，
以及 90 s `dataset_repo` 是 proxy 排队、fulltext 下载、timeout 还是 JSON repair 所致。

## 2. 修复 A：空 repair 立即收敛（1 天）

涉及文件：

- `apps/api/app/services/agents/graph/nodes/targeted_repair.py`
- `apps/api/app/services/agents/graph/research_graph.py`
- `apps/api/app/services/agents/graph/nodes/quality_gate.py`

### 2.1 规则

`targeted_repair_node` 完成后新增明确状态，而不是让空 `search_plan` 隐式重跑：

| 条件 | 路由 | 状态与结果 |
|---|---|---|
| `n_queries > 0` | `paper_retriever` | 正常 repair，保留去重后的 query ID |
| `n_queries == 0` 且 weak 达可提升阈值 | `quality_gate` 的 `weak_promote` 分支 | 提升为 `needs_human_confirm` 的 evidence，不伪装为高置信 accept |
| `n_queries == 0` 且无可提升 weak | `final_recommendation` | `repair_no_query`，输出 evidence insufficient 与人工下一步 |

建议新增字段：`repair_outcome`（`queries_ready|no_query|exhausted`）、
`repair_no_query_reason`、`repair_query_ids`。`repair_rounds` 仍计数，避免空计划循环。

### 2.2 weak 提升不应直接硬编码为真

目前 `quality_gate.py` 已有 weak promotion，但 `zero_accept_repair` 会优先阻断
“0 accept + 3 weak”的情况，正是本 case 的 79 秒来源。实现时加 feature flag：

```text
PAPERAGENT_ZERO_ACCEPT_WEAK_POLICY=repair|promote|hybrid
PAPERAGENT_WEAK_PROMOTE_MIN=3
```

- `repair`：当前基线；
- `promote`：relation 为 `baseline|parallel` 的 weak 进入分析链，全部附
  `confidence=weak_promoted` 与 `needs_human_confirm=true`；
- `hybrid`（推荐实验臂）：先走确定性 query generator；只有生成至少一条**新且可执行**
  query 才调用 LLM repair，否则提升 weak 或显式终止。

确定性 generator 从 `topic_atoms + rejected/weak title tokens + 缺口类型` 生成最多 2 条 query。
LLM 只负责选择/解释，不能成为唯一 query 来源。这与 Re5 的“LLM 作路由、query 由 skill atoms
确定化”方向一致。

### 2.3 单测

- [ ] 空 repair 不得再次调用 `paper_retriever`。
- [ ] 空 repair 只产生一次终态 trace，`repair_rounds` 不可无限增加。
- [ ] 被提升 weak 保留原 verdict/provenance，不能变成 `accept`。
- [ ] 非空且重复 query 视作空 repair；非空新 query 才允许检索。

## 3. 修复 B：展开为空时跳过第三轮 verify（0.5 天）

涉及文件：

- `apps/api/app/services/agents/graph/nodes/citation_expander.py`
- `apps/api/app/services/agents/graph/research_graph.py`
- `apps/api/app/services/agents/graph/nodes/verify.py`

将 `citation_expander -> verify` 改为条件边：

```text
n_expanded > 0  -> verify(expanded_only)
n_expanded == 0 -> quality_gate(continue)
```

必须同时移除 `verify_node` 中“citation_done 且 `expanded_papers` 空时回退
`paper_candidates`”的行为。该回退可以在 repair 检索轮使用，但不得用于 citation expansion
轮；用显式 `verify_scope=search|expanded` 区分两种情形，禁止用 `citation_done` 猜测。

验收：输入已有 7 accepted、`expanded_papers=[]` 时，verify 调用数为 0，最终仍保留 7 篇；
输入 1 篇新 expanded paper 时，只验证这一篇并与旧 accepted 去重合并。

## 4. 10 case 门控实验（2 天）

先不以一个 YOLO case 改写全局策略。准备 10 个固定、UTF-8 保存的 replay（每类至少 2）：

| 分层 | 观察目标 |
|---|---|
| 0 accept + >=3 weak | weak promotion 是否保住可用 evidence |
| 1--2 accept | 修复是否带来净新增且改变可行性结论 |
| >=3 accept | citation expansion 是否有净新增贡献 |
| 0 candidate | 正确 blocked，不“修复”出幻觉 |
| 多论文 / 高噪声 | expansion 对 survey、baseline、repo 的边际贡献 |

对每个 case 固定 provider/profile/超时，并跑三个臂：`repair`、`promote`、`hybrid`。保存
`trace_full.json`、状态快照、论文 verdict、最终建议；搜索 API 的波动须记录，不能把一次网络失败
算为策略收益。

判定指标：

- 延迟：p50、p95、总 LLM calls、空 repair 次数、空 expansion verify 次数；
- 质量：accepted/weak 的人工抽检准确率、baseline 数、可验证的 dataset/repo 数、
  final recommendation 是否从有证据变为无证据；
- 安全：弱提升的标记完整率 100%，不能产生无来源的 accept。

默认切换条件：`hybrid` 相比 `repair` 的中位墙钟下降 >= 20%，且人工抽检的有效 evidence
不下降超过 5%；否则只合入“空 repair / 空 expansion”两条确定修复。

## 5. 分析链：先验证并行，再实施两条候选路径（3--4 天）

当前代码写出了 `work_package -> innovation_extractor` 与 `work_package -> sota_matcher` 的 fan-out，
但 trace 总墙钟与各节点耗时几乎相加；需先用第 1 节埋点验证实际调度。仅增加 graph edge
不等于 provider 端并发。

### 方案 P：依赖图并行（默认候选）

重排为下列 superstep；节点仍各自 schema 校验与 fallback：

```text
feasibility
  -> parallel [work_package, sota_matcher, innovation_extractor]
  -> parallel [narrative_builder, optimization_advisor]
  -> devils_advocate
```

理由：当前 `innovation_extractor` 只读取 `topic/baselines/parallels`，不读取 work package；
`optimization_advisor` 读取 feasibility/innovation/baselines/parallels，不读取 narrative；
只有 `devils_advocate` 需要 narrative、innovation、work package。

实施约束：

- 采用 LangGraph 支持的 async/`Send` 或显式 `asyncio.to_thread`，并在 provider 层设
  `Semaphore(2)`，不要把 8 个长请求同时压向 OpenCode proxy；
- 等待并发任务时收集 typed failure，单个失败只触发该节点 fallback；
- 不允许并发节点写同一 state key；合并只发生在 barrier 后；
- 若 provider probe 显示并发排队/429，自动降级为 bundle 或串行，不把失败放大。

### 方案 B：Evidence Packet + Bundle Synthesis（快速模式候选）

用一个 context compiler 截断并编号 evidence（paper/baseline/dataset/repo 的 ID、标题、摘要、
置信度），一次调用产生分段 JSON：

```json
{
  "work_packages": [],
  "sota_comparison": {},
  "innovation_points": [],
  "stitching_plan": {},
  "research_narrative": {},
  "optimization_directions": {},
  "evidence_claim_map": []
}
```

随后保留一次独立 `devils_advocate` 调用。总计约 2 次 LLM 调用，而不是 6--7 次。
这不是暴露 CoT：prompt 只要求可审计的 `evidence_claim_map` 和简短理由，不请求或保存隐藏推理。

风险与护栏：bundle 的一个字段坏掉不能废弃整个结果；按 section 做 schema validation，坏 section
回退到对应 heuristic 或方案 P 的单节点重试。`innovation_points` 继续走 binding validator，
不能因 bundle 绕过证据绑定。该模式先以 `ANALYSIS_MODE=bundle` 灰度，不替换默认链。

### dataset_repo 专项

它已使用 `ThreadPoolExecutor(max_workers=4)`，但本 case 是 7 次 LLM 全失败、90.304 s。
优先修复 failure amplification，而不是继续提高 worker 数：

1. 先从第 1 节字段确认每次是否经历 `call_json` formatter 递归和 validator repair；
2. `DATASET_REPO_NODE_BUDGET_S=25`，超预算取消未开始任务并返回明确 partial；
3. 先做 GitHub URL / paper metadata / arXiv 元数据确定性提取；LLM batch 至多处理 top-3 的
   高价值论文，或一次性处理带 ID 的小批列表；
4. 若该 profile 连续 2 次失败，本 run 禁用后续 dataset LLM，保留 provenance=`heuristic/partial`。

## 6. 对比验收与回滚

| 项目 | 合入阈值 | 立即回滚条件 |
|---|---|---|
| 空 repair 退出 | 0 次空 query 重检索 | final recommendation 丢失原有 evidence |
| 空 expansion 跳 verify | 0 次空扩展复验 | 已 accepted 被清空或新增论文未验证 |
| 方案 P 并行 | 分析段 p50 降 >=35%，质量指标不降 >5% | 429/timeout 增加 >=10% 或 state merge 冲突 |
| 方案 B bundle | 分析段 p50 降 >=50%，section 校验 >=95% | 任一无证据创新点越过 binding validator |
| dataset budget | p95 <=35 s，partial 可见 | 证据被静默丢弃或错误标记为 found |

完成后输出 `tmp_re6_perf/<run_id>/`：`trace_full.json`、`latency_summary.json`、
`provider_call_timeline.json`、`quality_diff.json`、`decision.md`。先合入 A/B 的确定修复；
weak policy、并行模式和 bundle 模式均由 10 case 数据决定默认值。
