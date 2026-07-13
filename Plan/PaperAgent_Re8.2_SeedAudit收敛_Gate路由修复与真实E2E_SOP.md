# PaperAgent Re8.2：Seed Audit 收敛、Gate 路由修复与真实 E2E SOP

> Status: Ready for execution  
> Date: 2026-07-14  
> Predecessor: Re8.1 研究质量恢复与 Tailor 收敛诊断  
> Canonical path: `Plan/PaperAgent_Re8.2_SeedAudit收敛_Gate路由修复与真实E2E_SOP.md`

---

## 0. 结论与执行原则

Re8.1 已证明 Tailor LLM 可以在两轮内返回 `pass`。当前长期阻塞来自两个工程问题：

1. `final_review_gate` repair 后重复进入已通过的 `tailor_gate`，旧 round 被继续累计，最终 cap → `unresolved`；
2. `xlm_r S1` 与 `yolo_steel S2` 需要 Seed Repair 2.0，基础标题匹配不足以处理标题别名、作者年份冲突和无稳定 identifier 的情况。

执行者不得继续泛化调 Prompt。先修确定性路由，再修 Seed Candidate 检索和消歧，最后真实重跑。

### 不可修改的硬约束

- `REFLECTION_GATE_MAX_ROUNDS=2`；
- ablation 最少 4 项；
- `fused_verdict=BLOCKED` 时 `quality_pass=false`；
- 无 traceable `evidence_delta` 的 gap 不得 satisfied；
- 不得恢复任意结果批量满足 gap 的 fallback；
- 不得修改 fixture 或结果文件伪造 PASS；
- 所有接口修改应 additive 或保持兼容。

---

# 1. 总体流程

```text
WP0 冻结基线
  ↓
WP1 修 Gate 重入与 cycle 计数
  ↓ vit_dr smoke
WP2 Seed Repair 2.0
  ↓ xlm_r S1 / yolo_steel S2 定向测试
WP3 Seed Audit reason code 与 repair target
  ↓
WP4 三案例真实重跑
  ↓
WP5 真实前后端 E2E（禁止 page.route mock）
  ↓
WP6 标准交接包与最终决策
```

每个 WP 必须采用：

```text
Inspect → Reproduce → Minimal patch → Unit tests → Regression → Real case → Artifact → Decision
```

---

# 2. WP0：冻结与复现

## 2.1 操作

1. 记录当前 HEAD、Python、Node、模型、网络策略；
2. 保存 Re8.1 三案例最终结果；
3. 跑 Re8 相关测试；
4. 不修改代码，复现一次 `vit_dr`；
5. 保存 graph trace、每个 Gate 的 round、generated_by 和 repair target。

输出：

```text
artifacts/re8_2/baseline/
  manifest.json
  vit_dr_before.json
  vit_dr_trace_before.jsonl
  known_failures.json
```

## 2.2 执行提示词

```text
你正在执行 PaperAgent Re8.2 WP0。不要修改代码。

目标：冻结当前 master HEAD，并复现 vit_dr 的 Gate 重入问题。

请完成：
1. 读取 Re8.1 SOP、artifacts/re8_0/final/decision.md、当前 graph 和 reflection gate 实现。
2. 记录 commit、环境、模型、网络策略、REFLECTION_GATE_MAX_ROUNDS、ablation 门槛。
3. 运行 Re8 相关测试。
4. 真实运行 vit_dr，保存完整 trace。
5. 输出每次 tailor_gate/final_review_gate 的：cycle、round_idx、verdict、generated_by、rationale、repair target、输入摘要。
6. 明确指出：Tailor LLM 第一次 pass 后，哪些路径导致它再次被执行并最终 cap。
7. 不得调 Prompt，不得修改 round cap，不得改结果文件。

交付：artifacts/re8_2/baseline/manifest.json、vit_dr_before.json、vit_dr_trace_before.jsonl、known_failures.json。
```

---

# 3. WP1：Gate 重入与 cycle 修复

## 3.1 首选方案 A：输入指纹复用已通过 Gate

### 实现

在 `ResearchState` 增加：

```python
last_gate_pass: dict[str, dict[str, Any]]
gate_cycle_id: dict[str, int]
```

Tailor Gate pass 记录：

```python
{
    "verdict": "pass",
    "round_idx": 1,
    "cycle_id": 0,
    "input_fingerprint": "...",
    "generated_by": "llm",
    "rationale": "..."
}
```

新增：

```python
def _tailor_gate_input_fingerprint(state: ResearchState) -> str:
    ...
```

指纹只包含稳定字段：

- `tailored_method`；
- `evidence_gaps`；
- gap attribution 摘要；
- `seed_cards`；
- `ablation_matrix`。

不得包含 timestamp、trace id、elapsed time。

在 `tailor_gate_node` 开头：

```python
previous = state.get("last_gate_pass", {}).get("tailor_gate")
current_fp = _tailor_gate_input_fingerprint(state)
if previous and previous["verdict"] == "pass" and previous["input_fingerprint"] == current_fp:
    return reuse_previous_pass(previous)
```

复用时：

- 不调用 LLM；
- 不增加 round；
- 输出 `reused_previous_pass=true`；
- 保留原 rationale；
- 写入 ledger 和 final package。

输入发生变化时：

- `gate_cycle_id["tailor_gate"] += 1`；
- 新 cycle 的 round 从 0 开始；
- 每个 cycle 仍最多 2 轮；
- 旧 cycle 不能污染新 cycle。

## 3.2 备选方案 B：按 repair target 跳过 Tailor Gate

若方案 A 与现有 state 合同冲突，则修改 final review 输出：

```json
{
  "verdict": "revise",
  "repair_target": "evidence_context|tailor|seed_resolver",
  "reason_code": "..."
}
```

路由：

- 证据缺失 → `evidence_context`；
- 方法结构失效 → `tailor`；
- seed 不可靠 → `seed_resolver`。

当 repair target 不是 `tailor` 且 tailored_method 未变化时，不得再次执行 Tailor Gate。

## 3.3 备选方案 C：Gate 状态机

若 A/B 仍无法稳定表达，建立：

```python
GateStatus = Literal["not_run", "passed", "needs_recheck", "capped"]
```

只有上游 dependency version 改变时，`passed → needs_recheck`。依赖版本：

```python
{
  "seed_version": int,
  "evidence_version": int,
  "method_version": int
}
```

Tailor Gate 只依赖 `evidence_version + method_version`，不因 final review 自身 round 改变而重跑。

## 3.4 选择规则

- 优先 A：改动最小、审计最好；
- A 无法兼容现有 state 时采用 B；
- 路由已高度复杂、多个 Gate 都有同类问题时采用 C；
- 禁止简单全局 reset round_idx，因为会隐藏循环。

## 3.5 必测

至少 10 个测试：

1. pass + fingerprint 不变 → 复用；
2. 复用时不调用 LLM；
3. 复用时 round 不增加；
4. 复用结果写入 trace；
5. evidence-only repair 不消耗 Tailor round；
6. method 改变 → 新 cycle；
7. 新 cycle 最多 2 轮；
8. 旧 cycle 不污染新 cycle；
9. final review target=seed_resolver 时 Tailor 不重跑；
10. BLOCKED/quality 硬约束无回归。

## 3.6 执行提示词

```text
执行 Re8.2 WP1。目标是修复“Tailor 已 pass，但 final_review repair 后重复进入 Tailor 并累计到 cap”的确定性路由 bug。

先阅读 research_graph.py、reflection_gates.py、state.py、content.py 和 Re8.1 trace。

按以下优先级实现：
A. Tailor 输入 fingerprint + last_gate_pass 复用；
B. 若 A 与现有状态合同冲突，使用 repair_target 路由跳过无关 Gate；
C. 若多个 Gate 均存在同类问题，使用 dependency-version Gate 状态机。

禁止：
- 提高 REFLECTION_GATE_MAX_ROUNDS；
- 无条件 reset round_idx；
- 删除 final review repair；
- 将 unresolved 改名为 pass；
- 修改 demo 结果。

必须先写失败测试，再改实现。完成后运行 vit_dr 真实 smoke。验收目标：vit_dr 不再因 Tailor 重入而 unresolved，trace 中能看到 reused pass 或明确跳过原因。

提交中说明采用 A/B/C 哪个方案、为什么、未采用方案的原因。
```

---

# 4. WP2：Seed Repair 2.0

## 4.1 统一候选模型

```python
class SeedCandidate(TypedDict, total=False):
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    arxiv_id: str | None
    canonical_url: str | None
    abstract: str
    venue: str | None
    sources: list[str]
    title_score: float
    author_score: float
    year_score: float
    abstract_score: float
    identifier_score: float
    total_score: float
    confidence: str
    conflicts: list[str]
```

Crossref、Semantic Scholar、OpenAlex、arXiv 全部先归一化到此模型。

## 4.2 检索流程

新增：

```python
async def _fetch_seed_candidates(title, authors=None, year=None, abstract_hint=None):
    ...
```

并行构造：

1. 完整标题；
2. 去副标题标题；
3. 第一作者姓氏 + 核心标题词；
4. 年份 + 核心标题词。

标题 normalization：

- Unicode normalize；
- lowercase；
- 去标点；
- 去冒号副标题；
- acronym/全称 alias；
- 常见前缀如 `BERT:` 不作为否决差异。

## 4.3 评分方案 A（默认）

```text
total = 0.35 title + 0.25 author + 0.15 year + 0.15 abstract + 0.10 identifier
```

阈值：

- `>=0.85` 且无关键冲突 → verified；
- `0.70–0.85` → ambiguous/disambiguation；
- `<0.70` → not_found 或 ambiguous。

关键冲突：第一作者不符、年份差 >2、DOI 指向不同论文、来源作者集合无法解释。

## 4.4 评分方案 B（保守）

对于 false verification 风险较高的领域：

```text
verified 必须满足：
(title >= 0.88 AND author >= 0.70)
OR identifier_score == 1.0
```

若 author 缺失，不允许仅凭 title verified，必须双源一致或有 abstract 支持。

## 4.5 评分方案 C（学习排序，暂不默认）

若规则评分在 20+ 扩展集上仍不稳定，可保存人工标注 pair，训练简单 logistic/ranking model。Re8.2 不要求上线，仅允许作为实验分支，不得替代 A/B 的可解释结果。

## 4.6 LLM 候选消歧

只在以下情况调用：

- 2–5 个候选；
- top1-top2 <0.08；
- 至少一项 score >=0.70。

LLM 不能检索或造候选，只能选择已有候选或 reject all。

输出合同：

```json
{
  "selected_index": 0,
  "confidence": "high|medium|low",
  "reason": "...",
  "reject_all": false
}
```

low confidence 或 reject_all 均不得 verified。

## 4.7 两个具体案例

### xlm_r S1

将 BERT 长标题和去 `BERT:` 的标题视为 alias。预期 top1 为原 BERT 论文，并获得 DOI 或 arXiv 标识。

### yolo_steel S2

从现有 CASES/原始材料补齐：title、Song/Yan 作者、year、可得 abstract hint。若仍近分，进入 LLM 消歧；无法高置信选择则保持 ambiguous，但必须输出候选和明确 reason code。

## 4.8 执行提示词

```text
执行 Re8.2 WP2：实现 Seed Repair 2.0，直接解决 xlm_r S1 BERT title mismatch 与 yolo_steel S2 Song&Yan ambiguous。

要求：
1. 统一 Crossref/S2/OpenAlex/arXiv 候选结构。
2. 支持完整标题、去副标题、作者+关键词、年份+关键词查询。
3. 实现 title/author/year/abstract/identifier 可解释评分。
4. 默认使用方案 A；出现误验风险时切方案 B；方案 C 只做实验，不直接上线。
5. LLM 只允许在近分候选中选择，不得创造候选。
6. 所有 verified 保存 sources、scores、conflicts、all_candidates。
7. false verification rate 必须为 0。
8. NetworkPolicyGuard 必须继续生效。

先新增 xlm_r S1 和 yolo_steel S2 的失败 fixture，再实现。至少补 15 个测试，包括 alias、年份冲突、作者冲突、abstract 支持、近分 LLM、reject_all、低置信度、双源冲突和不存在论文。
```

---

# 5. WP3：Seed Audit Gate 结构化 reason code

新增 reason code：

```text
SEED_NOT_FOUND
SEED_LOW_CONFIDENCE
SEED_SOURCE_CONFLICT
SEED_AUTHOR_MISMATCH
SEED_YEAR_MISMATCH
SEED_IDENTIFIER_CONFLICT
SEED_FULLTEXT_UNAVAILABLE
SEED_VERIFIED
```

输出：

```json
{
  "verdict": "pass|revise|unresolved",
  "reason_code": "SEED_LOW_CONFIDENCE",
  "seed_id": "S2",
  "candidate_count": 3,
  "top_score": 0.78,
  "repair_target": "seed_resolver"
}
```

禁止只返回自然语言 rationale。

### 提示词

```text
执行 Re8.2 WP3。把 seed_audit_gate 从仅有自然语言 rationale 升级为结构化 reason_code + repair_target。

保持现有 verdict 兼容；新增字段必须 additive。所有 revise/unresolved 必须指出 seed_id、candidate_count、top_score 和 repair_target。更新前端类型与展示，但不得把 unresolved 显示成 success。
```

---

# 6. WP4：真实三案例重跑

顺序：

1. `vit_dr`：只验证 Gate 重入修复；
2. `xlm_r`：验证 Gate 重入 + BERT Seed Repair；
3. `yolo_steel`：验证 Song&Yan 消歧 + 已收敛 Tailor 路径。

保存：

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
- `vit_dr` 不得因 Tailor 重入 blocked；
- `xlm_r` seed_audit 不再因 BERT mismatch unresolved；
- `yolo_steel` S2 必须 verified，或以结构化低置信候选诚实 unresolved；
- 若失败，必须已转移到真实 novelty/low-bar 科研质量问题，而非路由或 seed 工程错误。

### 提示词

```text
执行 Re8.2 WP4。严格按 vit_dr → xlm_r → yolo_steel 顺序真实运行，不并行，不使用旧 artifact 覆盖。

每题输出完整 seed candidate、Gate cycle、repair target、fused verdict、quality reasons。任何一题出现 crash、contract regression、假阳性时立即停止并修复。

禁止为达到 2/3 非 BLOCKED 而放宽 Gate、提高 round cap、降低 ablation 或修改 CASES 的真实语义。
```

---

# 7. WP5：真实前后端 E2E

Playwright 不得使用 `page.route()` mock 作为最终验收。

流程：

1. 启动真实 API；
2. 启动真实前端 dev server；
3. 输入 DOI `10.18653/v1/N19-1423` 或另一个稳定公开 DOI；
4. 创建任务；
5. 轮询真实状态；
6. 检查 Seed、Gate cycle、repair、fused verdict、错误状态；
7. 下载 final package；
8. 对比导出 JSON 与后端返回。

若真实模型成本过高，可增加 deterministic replay，但 replay artifact 必须来自本次真实后端运行，不能手写 fixture。

### 提示词

```text
执行 Re8.2 WP5。现有 Playwright page.route mock 只保留为 UI 单测，不算真实 E2E。

启动真实 backend/frontend，提交一个稳定 DOI，等待任务完成，验证状态轮询、Gate rounds、错误显示、final package 下载及前后端 JSON 一致性。保存截图、network log、后端 run id 和导出文件。
```

---

# 8. WP6：标准交接包

必须生成标准文件名：

```text
artifacts/re8_2/final/
  manifest.json
  metrics.json
  decision.md
  regression_report.json
  e2e_report.json
  known_gaps.json
```

`decision.md` 必须区分：

- verified；
- inferred；
- proposed；
- unknown。

最终状态：

- `PASS`：2/3 非 BLOCKED、1/3 quality true、真实 E2E 通过；
- `PARTIAL`：工程阻塞消除，但真实科研 Gate 仍拒绝；
- `NO-GO`：Seed 仍不能可靠确认或 Gate 路由仍产生假状态。

---

# 9. 自主操作权限

执行者可以直接：

- 修改代码与测试；
- 新建 artifacts；
- 提交小步 commit；
- 在 A/B/C 方案中自行选择；
- 某方案失败后切换下一方案；
- 更新本 SOP checkbox 与 decision.md。

必须报告用户后才能：

- 修改 round cap；
- 降低 ablation 门槛；
- 改 quality_pass 定义；
- 删除现有真实失败样本；
- 引入付费服务或大规模计算。

---

# 10. Commit 建议

```text
1. test(re8.2): reproduce tailor gate re-entry and seed ambiguity
2. fix(re8.2): reuse passed gates by stable input fingerprint
3. feat(re8.2): add multi-source seed candidate ranking
4. feat(re8.2): add constrained LLM seed disambiguation
5. feat(re8.2): add structured seed audit reason codes
6. test(re8.2): rerun three authoritative cases
7. test(re8.2): run real backend frontend e2e
8. docs(re8.2): finalize standardized handoff package
```

每个 commit 必须可以独立解释、测试，并避免把代码、运行产物和文档全部混成一个超大提交。
