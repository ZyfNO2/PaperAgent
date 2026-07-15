# PaperAgent Re8.2 当前状态与可用性 Roadmap

> Status: **ACTIVE**  
> Updated: **2026-07-16**  
> Baseline: `master@dffce680ea8ca02d0a76112f8e5641a14c678e6f`  
> Canonical execution contract: [`PaperAgent_Re8.2_EXECUTION_CONTRACT.md`](./PaperAgent_Re8.2_EXECUTION_CONTRACT.md)  
> Detailed SOP: [`PaperAgent_Re8.2_SeedAudit收敛_Gate路由修复与真实E2E_SOP.md`](./PaperAgent_Re8.2_SeedAudit收敛_Gate路由修复与真实E2E_SOP.md)

---

## 1. 当前结论

PaperAgent 当前处于 **engineering alpha / internal demo** 阶段：

- Agent 主流程、Seed/证据处理、Tailor、Reflection Gate、Final Research Package、API 和 React 页面均已有实现；
- Re8.2 WP1 的 Gate evaluation/reuse/cycle 主体已经合入 `master`；
- WP1 的二次 code review 修复已完成并通过 CI，但仍在 Draft PR #2，尚未合入 `master`；
- 真实 Provider smoke、Seed Repair 2.0、三案例真实重跑和无 Mock 前后端 E2E 尚未完成；
- 因此当前可以用于继续开发、离线回归和受控演示，不能表述为稳定生产可用。

### 1.1 当前证据

| 项目 | 当前状态 | 证据 |
|---|---|---|
| WP1 第一版 Gate reuse/cycle | 已合入 | PR #1 |
| WP1 post-merge hardening | 已实现、待合并 | Draft PR #2 |
| focused Re8.2 Gate tests | 34/34 PASS | PR #2 CI |
| isolated Re8 regression | 802/802 PASS | PR #2 CI |
| React production build | PASS | PR #2 CI |
| full API regression delta | 0 个 head-only failure/error | PR #2 CI |
| full API historical failures | 52 个仍存在 | PR #2 CI |
| real Mistral `vit_dr` smoke | 未验证 | execution environment/provider pending |
| real backend/frontend E2E | 未执行 | WP5 pending |

Relevant links:

- [PR #2 — Re8.2 post-merge review](https://github.com/ZyfNO2/PaperAgent/pull/2)
- [Issue #3 — API/frontend contract parity](https://github.com/ZyfNO2/PaperAgent/issues/3)
- [`artifacts/re8_2/wp1/HANDOFF.md`](../artifacts/re8_2/wp1/HANDOFF.md)
- [`artifacts/re8_2/postmerge-code-review/HANDOFF.md`](../artifacts/re8_2/postmerge-code-review/HANDOFF.md)

---

## 2. 不可变更的质量边界

以下约束继续适用于所有后续工作包：

- `REFLECTION_GATE_MAX_ROUNDS=2`；
- ablation 最少 4 项；
- `fused_verdict=BLOCKED => quality_pass=false`；
- 无 traceable `evidence_delta` 的 gap 不得标记为 satisfied；
- 不得恢复任意结果批量满足 gap 的 fallback；
- 不得修改 fixture、阈值或结果文件伪造 PASS；
- Mock/Fake/rule fallback 不能作为真实 Provider 或真实 E2E 证据；
- Secret 不得进入仓库、artifact、trace 或日志；
- Final Research Package 保持 7 个 canonical sections；
- 接口变更必须 additive 或提供明确兼容迁移。

---

## 3. 执行顺序

```text
R1 合并 WP1 hardening（PR #2）
  ↓
R2 API/frontend contract closure（Issue #3，WP1.5）
  ↓
R3 真实 Mistral vit_dr smoke
  ↓
R4 WP2 Seed Repair 2.0
  ↓
R5 WP3 Seed Audit reason_code / repair_target
  ↓
R6 WP4 三案例真实重跑
  ↓
R7 WP5 无 Mock backend/frontend E2E
  ↓
R8 全仓测试债务收敛 + WP6 标准交接
  ↓
R9 可选：生产化基础设施
```

R2 属于 WP1 后的合同闭环，不修改 Seed Repair、Gate prompt、round cap 或质量阈值。R3 未完成前，不把 WP1 表述为真实 Provider 已验收。

---

## 4. Milestone 详情

## R1 — 合并 Gate hardening

**状态：READY / PENDING MERGE**

目标：把 PR #2 的二次 code-review 修复合入 `master`。

范围：

- skip/reuse 历史不消耗真实 evaluation round；
- stale pass cache 不得覆盖后续 revise/unresolved；
- skip cache invalidation 持久化；
- Gate execution metadata 不破坏七段 package contract；
- baseline-delta CI 阻断新增全量回归。

验收：

- PR head 未漂移；
- focused Gate suite 全绿；
- isolated Re8 全绿；
- frontend production build 通过；
- full API head-only failures/errors 为 0；
- 合并后在 `master` 重新运行最小回归。

交付：

- merged PR；
- merge SHA；
- master CI evidence；
- 更新 handoff 状态。

---

## R2 — API/frontend contract closure

**状态：OPEN — Issue #3**

目标：确保真实 HTTP summary、TypeScript 类型和页面展示表达同一个状态合同。

必须完成：

1. 将 CLI 等价的 runtime/contract/quality 判定抽到 import-safe pure module；
2. `/seeded-summary` 返回：
   - `runtime_pass`；
   - `contract_pass`；
   - `contract_pass_reasons`；
   - `quality_pass`；
   - `quality_pass_reasons`；
3. 导出 Tailor cycle、evaluation events、reuse events 和 reuse count；
4. 修正 `gate_results`、`evidence_gap_status` 和 nullable Gate 的 TypeScript 类型；
5. 未执行 Gate 显示 `not available`，不得崩溃或伪造 pass/fail；
6. `n_seeds_input` 优先使用原始 `candidate_seeds`；
7. 移除 Seed Audit 阶段错误的 `SEED_FULLTEXT_UNAVAILABLE` 语义；
8. 前端 NetworkPolicy 加入后端支持的 `cache_first`。

验收：

- 后端 contract tests；
- nullable Gate frontend tests；
- reuse/cycle 页面可见；
- production build 通过；
- package 仍为 7 sections；
- `BLOCKED => quality_pass=false` 无回归。

---

## R3 — 真实 Mistral `vit_dr` smoke

**状态：BLOCKED / NOT VERIFIED**

目标：验证 WP1 在真实 Provider 和真实 graph 路径中成立。

前置条件：

- Secret 通过运行时注入；
- 冻结 model ID、endpoint、max tokens、timeout 和成本上限；
- 执行环境能解析并访问 `api.mistral.ai`；
- R1/R2 的离线回归通过。

必须观察：

- Tailor 首次真实 evaluation 返回 pass；
- final review repair 回到 evidence path；
- Tailor semantic fingerprint 不变；
- trace 出现 `gate_pass_reused`；
- Tailor evaluation log 长度不增加；
- fused verdict 不再因 Tailor 重入 cap 而 BLOCKED。

网络不可达时只允许记录：

```text
BLOCKED BY EXECUTION ENVIRONMENT / KEY NOT VERIFIED
```

不得将网络问题推断为 Key 无效。

---

## R4 — WP2 Seed Repair 2.0

**状态：NOT STARTED**

目标：把 Seed Resolver 从基础标题匹配升级为多源、可解释、低假阳性的候选消歧系统。

范围：

- 统一 Crossref、Semantic Scholar、OpenAlex、arXiv 候选模型；
- stable candidate ID；
- title/author/year/abstract/identifier 分项评分；
- alias、副标题、acronym/full-name normalization；
- critical conflict 处理；
- 2–5 个近分候选的受约束 LLM disambiguation；
- LLM 只能选择已有候选或 reject all，不得创造候选；
- 保存 sources、scores、conflicts 和 all_candidates。

重点案例：

- `xlm_r S1`：BERT 长标题与去前缀 alias；
- `yolo_steel S2`：Song/Yan 作者、年份和摘要线索消歧。

验收：

- 至少 15 个新增 targeted tests；
- frozen candidate set 上 false verification rate = 0；
- NetworkPolicyGuard 继续生效；
- 无 identifier 且 author 缺失时不得仅凭高 title score verified。

---

## R5 — WP3 Seed Audit 结构化诊断

**状态：NOT STARTED**

目标：所有 Seed Audit revise/unresolved 都返回机器可路由、前端可解释的结构化结果。

目标输出：

```json
{
  "verdict": "revise",
  "reason_code": "SEED_LOW_CONFIDENCE",
  "seed_id": "S2",
  "candidate_count": 3,
  "top_score": 0.78,
  "repair_target": "seed_resolver"
}
```

要求：

- verdict 保持兼容；
- `reason_code`、`repair_target` additive；
- revise/unresolved 必须包含 seed 和候选上下文；
- 前端不得把 unresolved 显示为 success；
- fulltext acquisition failure 必须归属正确阶段。

---

## R6 — WP4 三案例真实重跑

**状态：NOT STARTED**

执行顺序固定：

1. `vit_dr`；
2. `xlm_r`；
3. `yolo_steel`。

每个案例保存：

```text
artifacts/re8_2/runs/<case>/
  run.json
  trace.jsonl
  seed_candidates.json
  seed_decision.json
  gate_cycles.json
  final_package.json
  metrics.json
```

验收：

- 至少 2/3 非 BLOCKED；
- 至少 1/3 `quality_pass=true`；
- `vit_dr` 不得因 Tailor 重入而 blocked；
- `xlm_r` 不得因 BERT alias 工程问题 unresolved；
- `yolo_steel` S2 verified，或以结构化低置信结果诚实 unresolved；
- 失败原因应转移到真实科研质量问题，而非路由或 Seed 工程错误。

---

## R7 — WP5 无 Mock 前后端 E2E

**状态：NOT STARTED**

目标：证明真实 API、真实任务执行、真实页面和导出 package 构成完整闭环。

流程：

1. 启动真实 API；
2. 启动真实 React 前端；
3. 提交稳定公开 DOI；
4. 轮询真实状态；
5. 检查 Seed、Gate cycle/reuse、repair、fused verdict 和错误状态；
6. 下载 final package；
7. 对比页面、HTTP summary、导出 JSON 和后端 state。

限制：

- `page.route()` mock 仅算 UI 单测，不算最终 E2E；
- deterministic replay 只能使用本次真实后端运行产生的 artifact；
- 不得手写 replay fixture 冒充真实运行。

验收产物：

- screenshot；
- browser/network log；
- backend run ID；
- exported package；
- E2E report；
- frontend/backend JSON consistency report。

---

## R8 — 全仓测试债务与 WP6 交接

**状态：PARTIAL / NOT STARTED**

当前完整 API suite 仍有历史失败。baseline-delta CI 可以阻止新增失败，但不能替代债务收敛。

处理方式：

1. 将每个历史失败分类为：
   - active defect；
   - obsolete test；
   - environment dependency；
   - intentional contract migration；
   - quarantined known failure；
2. active defect 必须修复；
3. obsolete test 必须删除或迁移并记录依据；
4. quarantine 必须有 owner、reason 和退出条件；
5. 最终生成标准交接包：

```text
artifacts/re8_2/final/
  manifest.json
  metrics.json
  decision.md
  regression_report.json
  e2e_report.json
  known_gaps.json
```

最终决策：

- `PASS`：2/3 非 BLOCKED、1/3 quality true、真实 E2E 通过；
- `PARTIAL`：工程阻塞消除，但真实科研 Gate 仍拒绝；
- `NO-GO`：Seed 仍不能可靠确认或 Gate 路由仍产生假状态。

---

## R9 — 可选生产化

**状态：OUT OF RE8.2 CORE SCOPE**

只有在 R1–R8 完成后，才进入公网或多人稳定使用所需的生产化：

- 持久化任务队列和任务恢复；
- 数据库与对象存储；
- 用户认证和多租户隔离；
- API 限流、配额和成本预算；
- Provider retry、timeout、circuit breaker；
- Secret manager；
- 结构化日志、指标和告警；
- 任务取消和幂等执行；
- PDF、用户材料、trace 和日志隐私策略；
- container/deployment/migration runbook。

R9 未完成前，不把当前本地 thread + local artifact 模式描述为生产级分布式任务系统。

---

## 5. 可用性分级

### Level A — Internal engineering alpha（当前）

允许：

- 离线回归；
- 开发调试；
- 受控演示；
- 展示 Agent graph、RAG、Gate、evidence attribution 和 CI 设计。

不允许宣称：

- 真实三案例已稳定收敛；
- Seed 消歧生产可靠；
- 真实 Provider 已验收；
- 全仓 CI 全绿；
- 公网生产可用。

### Level B — Self-use beta

最低门槛：

- R1–R3 完成；
- Issue #3 完成；
- 至少一个真实案例端到端完成；
- 启动、配置、错误处理和导出路径可复现。

### Level C — Portfolio/demo complete

最低门槛：

- R1–R7 完成；
- 三案例证据完整；
- 无 Mock E2E；
- 失败边界和非声明清晰；
- README、架构图、测试矩阵和 demo script 与代码一致。

### Level D — Production candidate

最低门槛：

- R1–R9 完成；
- 全量回归策略稳定；
- 任务持久化、认证、配额、监控、隐私和恢复机制完成；
- 经过真实用户和故障场景验证。

---

## 6. 最近三个执行批次

### Batch 1 — Gate hardening merge

```text
PR #2 review → ready-for-review → merge → master smoke
```

### Batch 2 — HTTP contract closure

```text
Issue #3 backend pure contract module
→ seeded-summary fields
→ frontend type/nullability
→ backend/frontend tests
```

### Batch 3 — Real WP1 verification

```text
runtime secret injection
→ vit_dr real Mistral run
→ Gate reuse trace audit
→ artifact + decision
```

在 Batch 3 完成前，不启动 WP2 实现分支。

---

## 7. 维护规则

每次 milestone 状态改变时，本文件必须同步更新：

- master SHA；
- PR/Issue 状态；
- verified implementation SHA；
- CI counts；
- real run evidence；
- blockers；
- next executable batch。

只记录已验证事实。推断、计划和未知项必须明确标注，不得把离线测试包装为真实 Provider/E2E 结果。
