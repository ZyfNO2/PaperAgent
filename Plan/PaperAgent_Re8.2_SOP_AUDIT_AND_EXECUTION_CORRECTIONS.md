# PaperAgent Re8.2 SOP 审计与执行修订

> Status: **REVISE BEFORE EXECUTION**  
> Audited repository: `ZyfNO2/PaperAgent`  
> Audited branch: `master`  
> Audited HEAD: `e811d2b7daf05b5140d3d9c6dfdc9a90584390a7`  
> Audited SOP: `Plan/PaperAgent_Re8.2_SeedAudit收敛_Gate路由修复与真实E2E_SOP.md`  
> Purpose: 在不改变 Re8.2 目标的前提下，补齐会直接影响实现正确性、可审计性和真实验收可信度的合同。

---

## 1. 最终判定

Re8.2 的问题拆分、WP 顺序和“不提高 round cap、不降低质量门槛”的方向正确，可以作为下一轮开发主线。

但当前版本不能直接按原文执行。以下问题必须先作为实现合同补齐：

1. Gate pass 复用事件与真实 evaluation round 没有分离，按当前代码结构实现会继续增加 round；
2. Tailor 输入 fingerprint 若直接包含完整 `seed_cards`，会把 `raw_input.pdf_bytes`、本地路径和非稳定字段带入哈希；
3. 方案 B 的 `repair_target/reason_code` 会被当前 `_normalize_gate_output()` 静默丢弃；
4. `SEED_FULLTEXT_UNAVAILABLE` 被放在 fulltext acquisition 之前的 Seed Audit Gate，阶段错误；
5. Seed Candidate 评分没有定义缺失信号、关键冲突和多源不可用时的优先级；
6. LLM 消歧只用数组下标，没有稳定候选 ID 和严格输出校验；
7. `false verification rate=0` 没有限定为冻结基准集观测结果，且缺少独立 holdout；
8. 真实 Provider/E2E 没有定义 secret、成本、模型版本和日志脱敏边界。

本文件对上述冲突条款具有优先解释权。实现完成后，应将有效修订合并回 canonical SOP，避免长期维护两套执行合同。

---

## 2. 已验证的仓库事实

### 2.1 Gate round 的当前定义

当前 `reflection_gates.py`：

```python
def _get_gate_rounds(state, gate_name):
    results = state.get("reflection_gate_results") or {}
    return len(results.get(gate_name, []))
```

`_run_gate()` 每次正常、fallback、skip 或 cap 结果都会通过 `_append_gate_result()` 追加到同一列表。

因此，“复用 pass 时追加一条 reused result，但 round 不增加”在当前合同下不成立。

### 2.2 Final Review repair 的真实路径

当前图路径为：

```text
final_review_gate revise
→ evidence_context
→ tailor_skill_adapter
→ tailor_gate
```

这会重新执行已通过的 Tailor Gate。现有 capped-downstream guard 只能避免已 capped 的 Tailor 被再次进入，不能复用已经 pass 的 Tailor 结果。

### 2.3 Seed card 含有不可直接 fingerprint 的字段

`SeedPaperCard.raw_input` 会保留原始输入；PDF 路径中还可能携带 `pdf_bytes`。完整序列化 `seed_cards` 会产生：

- 大对象哈希；
- bytes 非 JSON 可序列化问题；
- 本地路径和临时字段导致假变更；
- 不必要的敏感内容进入 trace 或调试产物。

### 2.4 Gate normalizer 当前只保留固定字段

`make_reflection_gate_result()` 和 `_normalize_gate_output()` 当前只保留：

```text
gate_name
verdict
round_idx
re_search_requests
unresolved_gaps
rationale
generated_by
```

LLM 即使返回 `repair_target` 或 `reason_code`，也会在 normalize 阶段消失。

### 2.5 Seed Audit 位于 Fulltext Acquisition 之前

当前图顺序为：

```text
seed_resolver
→ seed_audit_gate
→ fulltext_acquisition
→ paper_understanding
```

因此 Seed Audit Gate 不能基于尚未发生的下载结果输出 `SEED_FULLTEXT_UNAVAILABLE`。

---

## 3. WP1 强制修订：Gate 复用与 cycle 合同

### 3.1 采用方案 A，但必须使用“evaluation 与 reuse 分离”模型

新增状态建议：

```python
last_gate_pass: dict[str, dict[str, Any]]
gate_cycle_id: dict[str, int]
gate_reuse_events: list[dict[str, Any]]
```

也可以不新增 `gate_reuse_events`，仅把 reuse 写入 `trace_events` 与 `reasoning_ledger`。关键规则是：

> **reuse 不得追加到用于计算 evaluation round 的 `reflection_gate_results[gate]`。**

推荐行为：

```python
previous = last_gate_pass.get("tailor_gate")
current_fp = tailor_gate_input_fingerprint(state)

if previous_pass_matches(previous, current_fp):
    return {
        "last_gate_pass": unchanged,
        "reflection_gate_results": unchanged,
        "reasoning_ledger": [reuse_ledger_entry],
        "trace_events": [reuse_trace_event],
    }
```

Reuse trace 至少包含：

```json
{
  "gate_name": "tailor_gate",
  "event_type": "gate_pass_reused",
  "reused_previous_pass": true,
  "source_cycle_id": 0,
  "source_round_idx": 1,
  "input_fingerprint": "sha256:...",
  "generated_by": "reuse"
}
```

### 3.2 Round 定义

明确区分：

- `evaluation_round_idx`：真实 LLM/rule evaluation 次数；受 `REFLECTION_GATE_MAX_ROUNDS=2` 限制；
- `reuse_count`：复用次数；不受 evaluation cap 计数，但必须可审计；
- `cycle_id`：稳定输入发生语义变化后递增。

禁止继续用“所有 gate log 长度”同时表达以上三个概念。

### 3.3 Fingerprint 必须采用稳定投影

禁止直接 hash 整个 `ResearchState`、完整 `seed_cards` 或完整 `raw_input`。

推荐：

```python
def _tailor_gate_input_projection(state):
    return {
        "tailored_method": project_tailored_method(state.get("tailored_method")),
        "evidence_gaps": project_evidence_gaps(state.get("evidence_gaps")),
        "seed_identity": project_seed_identity(state.get("seed_cards")),
    }
```

`seed_identity` 只允许：

```text
seed_id
resolved_title
authors
year
doi
arxiv_id
canonical_url
existence_status
role
fulltext_status
```

必须排除：

```text
raw_input
pdf_bytes
local pdf path
trace_events
timestamps
elapsed time
provider request id
validation warning order
```

Canonical hash：

```python
payload = json.dumps(
    projection,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    default=_stable_json_default,
)
fingerprint = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

列表必须按稳定业务键排序，例如 `gap_id`、`seed_id`、module name；不能依赖异步返回顺序。

### 3.4 新 cycle 的触发条件

Tailor Gate 的 dependency projection 应至少包括：

- Tailor 方法语义输出；
- Evidence gap 的 `gap_id/status/evidence_delta`；
- 与方法选择相关的 Seed identity/role；
- ablation 和 compatibility 内容。

以下变化不得创建新 cycle：

- final review 自身 round；
- trace、ledger 新增；
-运行耗时；
- 相同候选的来源顺序变化；
- 前端展示字段变化。

### 3.5 方案 B 的最低合同

若选择 `repair_target` 路由，必须同步修改：

- `make_reflection_gate_result()`；
- `validate_reflection_gate_result()`；
- `_normalize_gate_output()`；
- `_make_gate_ledger()`；
- trace payload；
- final research package；
- API response schema；
- 前端 TypeScript 类型与展示。

新增字段建议：

```text
reason_code: str | None
repair_target: evidence_context | tailor | seed_resolver | None
cycle_id: int
input_fingerprint: str | None
reused_previous_pass: bool
```

所有字段 additive；旧 artifact 缺字段时必须安全默认。

### 3.6 WP1 增补测试

除 canonical SOP 的 10 项测试外，至少补充：

1. reuse 后 `len(reflection_gate_results[tailor_gate])` 不变；
2. reuse_count 增加但 evaluation round 不增加；
3. `pdf_bytes` 改变不影响 Tailor fingerprint；
4. gap 状态或 evidence_delta 改变会产生新 fingerprint；
5. 异步列表顺序变化不影响 fingerprint；
6. legacy gate result 缺新字段仍可读取；
7. 方案 B 下 normalizer 不丢 `repair_target/reason_code`；
8. reuse trace 和 ledger 指向原 pass 的 cycle/round。

---

## 4. WP2 强制修订：Seed Repair 2.0

### 4.1 统一候选必须有稳定 ID

`SeedCandidate` 增加：

```python
candidate_id: str
source_record_ids: dict[str, str]
query_variants: list[str]
source_status: dict[str, str]
```

`candidate_id` 应由 DOI/arXiv ID 优先生成；无 identifier 时由规范化 title + authors + year 的稳定摘要生成。

LLM 消歧必须返回 `selected_candidate_id`，不能只返回易受排序影响的 `selected_index`。

### 4.2 缺失信号必须有明确评分语义

固定权重公式必须说明缺失字段如何处理。采用以下一种，并在产物中记录：

#### 推荐：可用信号归一化

```text
weighted_sum = Σ(weight_i × score_i × available_i)
available_weight = Σ(weight_i × available_i)
normalized_score = weighted_sum / available_weight
```

但必须有最小证据组合门槛，防止仅凭单一 title 高分 verified。

#### 禁止

- 把缺失 author/year/abstract 默认当作 0 后仍沿用同一阈值；
- 把缺失信号当作完全匹配；
- 仅凭候选“带 DOI”就令 `identifier_score=1`，却不核对 DOI 是否与输入一致。

### 4.3 关键冲突优先级高于总分

所有方案 A/B 和 LLM 消歧均受以下硬约束：

```text
critical_conflict=true → existence_status != verified
```

关键冲突至少包括：

- 输入 DOI/arXiv ID 与候选 identifier 不一致；
- identifier 指向不同标题且无法由 alias 解释；
- 第一作者明确不一致；
- 年份差 >2 且无 online-first / preprint / proceedings 解释；
- 多个权威来源对 identifier 指向不同论文。

`identifier_score==1.0` 不能覆盖关键冲突。

### 4.4 Source failure 不得等同于 Not Found

新增 reason code：

```text
SEED_SOURCE_UNAVAILABLE
SEED_NETWORK_BLOCKED
SEED_RATE_LIMITED
SEED_QUERY_BUDGET_EXHAUSTED
```

如果所有来源均超时、429、被 NetworkPolicyGuard 拒绝或网络不可用，结果只能是 `ambiguous/unresolved`，不得是 `not_found`。

`not_found` 仅适用于：

- 至少一个权威来源成功响应；
- 查询预算已按计划执行；
- 没有满足最低候选门槛；
- source health 证据已保存。

### 4.5 LLM 消歧严格合同

调用条件沿用 canonical SOP，但输出改为：

```json
{
  "selected_candidate_id": "doi:10.xxxx/yyy",
  "confidence": "high|medium|low",
  "reason": "comparison using only supplied candidate fields",
  "reject_all": false
}
```

校验规则：

- candidate ID 必须来自输入候选集合；
- `reject_all=true` 时 selected ID 必须为空；
- low confidence 不得 verified；
- malformed JSON、未知 ID、越权引用外部论文均 fail closed；
- LLM 选择不能覆盖 critical conflict；
- prompt 与输出保存 candidate-set digest，不保存 secret。

### 4.6 Benchmark 与 holdout

将现有 20 条集定义为：

```text
frozen_regression_set
```

新增至少 10 条独立：

```text
holdout_acceptance_set
```

要求：

- 阈值和 alias 规则不得根据 holdout 单条结果迭代；
- 两个 authoritative case 可以进入 regression set，但不能是唯一验收依据；
- 报告 false positive、false negative、ambiguous、source unavailable 四类；
- “false verification rate=0”只能写成“冻结测试集观测到 0 次 false verification”；
- 不得宣称总体概率为 0。

### 4.7 查询预算与可重复性

每个 seed 必须记录：

```text
query variants
source request count
source status
cache hit/miss
elapsed time
candidate count before/after dedupe
score version
threshold version
```

真实测试允许 cache-first replay，但最终 authoritative evidence 至少包含一次 online run。

---

## 5. WP3 强制修订：Reason Code 的阶段归属

### 5.1 Seed Audit Gate 可用 reason code

```text
SEED_NOT_FOUND
SEED_LOW_CONFIDENCE
SEED_SOURCE_CONFLICT
SEED_AUTHOR_MISMATCH
SEED_YEAR_MISMATCH
SEED_IDENTIFIER_CONFLICT
SEED_SOURCE_UNAVAILABLE
SEED_NETWORK_BLOCKED
SEED_RATE_LIMITED
SEED_METADATA_INSUFFICIENT
SEED_VERIFIED
```

### 5.2 从 Seed Audit Gate 移除

```text
SEED_FULLTEXT_UNAVAILABLE
```

原因：当前 Seed Audit Gate 在 `fulltext_acquisition` 之前执行。

Fulltext failure 应由以下位置之一负责：

- `fulltext_acquisition` 的结构化输出；
- `paper_understanding` 的 parse/fulltext reason code；
- downstream final review 对信息充分性的判断。

除非 Re8.2 明确调整图顺序并补齐兼容测试，否则不得让 Seed Audit Gate 假装知道尚未执行的 fulltext 结果。

### 5.3 Reason code 结构

所有非 pass 结果至少包含：

```json
{
  "verdict": "revise|unresolved",
  "reason_code": "SEED_LOW_CONFIDENCE",
  "seed_id": "S2",
  "candidate_count": 3,
  "top_score": 0.78,
  "repair_target": "seed_resolver",
  "source_status": {
    "crossref": "ok",
    "semantic_scholar": "rate_limited",
    "openalex": "ok",
    "arxiv": "not_applicable"
  }
}
```

禁止仅靠自然语言 rationale 推断 repair target。

---

## 6. WP4 验收修订

保留 canonical SOP 的三案例顺序与主门槛，并增加：

- 每题必须记录运行 commit、provider model、prompt/score version；
- 所有 candidate decision 必须可由保存的候选和评分重算；
- source unavailable 与 not_found 分开计数；
- Gate reuse 必须展示 original cycle/round 与 reuse event；
- 若 provider、外部检索源或 frontend 任一不可用，状态为 `BLOCKED / NOT VERIFIED`，不得用 replay 冒充本次 online E2E；
- replay 只验证确定性回归，不关闭 real-provider gate。

---

## 7. WP5 真实 Provider 与前后端 E2E 修订

### 7.1 Secret 处理

- API key 只能通过进程环境或本地未跟踪 secret file 注入；
- 禁止写入 git、artifact、Playwright trace、network log、截图、exception repr；
- 日志只允许记录 provider 名称、model、request id 的脱敏值、latency、token/cost 汇总；
- 测试结束后清理临时环境和生成文件；
- CI 中没有专用 Secret 时不得上传本地 key。

### 7.2 Provider 固定

真实验收必须记录：

```text
provider
base URL
model identifier
SDK/HTTP client version
timeout
max tokens
temperature/reasoning settings
retry policy
```

模型标识必须在测试开始时冻结；不得在三案例中途自动切换模型而不记录。

### 7.3 成本与调用上限

执行前定义：

```text
max provider calls per case
max tokens per call
max total elapsed time
max retry count
stop-on-first-contract-failure
```

超预算时状态为 `blocked_budget`，不得自动降低质量门槛。

### 7.4 Mistral 真实验证顺序

在实现 commit 和离线/CI 回归均通过后：

1. 只运行一个最小 JSON-contract Provider smoke；
2. 运行 `vit_dr` gate-reuse smoke；
3. 运行 `xlm_r` Seed Repair authoritative case；
4. 仅在前两步无 contract/secret/log 问题后运行 `yolo_steel`；
5. 最后启动真实 backend/frontend，完成一个稳定 DOI 的 Playwright E2E；
6. 检查日志、trace、截图和导出包均未包含 key。

任何一步出现：

- 非 JSON 输出；
- schema 被 normalizer 静默降级；
- secret 泄露；
- provider 429/5xx 被误判为科研失败；
- source unavailable 被误判为 not_found；

必须停止后续真实调用并先修复。

---

## 8. 修订后的最小执行顺序

```text
WP0-A 冻结 HEAD、环境和 provider 配置
WP0-B 复现 vit_dr，并证明 pass 后重入路径
WP1-A 先修 evaluation/reuse/cycle 合同
WP1-B 定向测试 + vit_dr Mistral smoke
WP2-A SeedCandidate 稳定 ID、source status、评分合同
WP2-B regression + holdout，不调用 LLM
WP2-C 受限 LLM 消歧
WP3 reason code / repair target 全链路扩展
WP4 三案例真实重跑
WP5 真实 backend/frontend E2E
WP6 标准交接包与最终决策
```

不得在 WP1 Gate 合同未稳定前并行修改 Seed Repair 和前端类型；否则难以区分 round bug、候选 bug 和展示 bug。

---

## 9. 合并前验收矩阵

| Gate | 必须证据 | 阻塞条件 |
|---|---|---|
| SOP contract | 本修订已合并回 canonical SOP 或明确引用 | 两份文档冲突 |
| Gate reuse | pass 复用不增加 evaluation round | reuse 仍使 round 增长 |
| Fingerprint | 稳定投影、顺序不敏感、排除 pdf_bytes | hash 完整 state/seed raw input |
| Repair target | normalizer/schema/API/frontend 均保留字段 | 字段被静默丢弃 |
| Seed scoring | 缺失信号、critical conflict、source failure 均有测试 | identifier 高分覆盖冲突 |
| LLM disambiguation | stable candidate ID + strict validation | 仅 selected_index 或未知候选可通过 |
| Benchmark | frozen regression + independent holdout | 同一集合调参并验收 |
| Real Provider | key 不落盘/不入日志，model 与预算冻结 | secret 泄露或 provider 未记录 |
| Real E2E | 真实 backend/frontend，无 page.route mock | replay/mock 冒充真实 E2E |

---

## 10. 审查结论

当前 canonical SOP：**PASS WITH REQUIRED CORRECTIONS / NOT READY FOR CODE EXECUTION**。

修订后可进入 Re8.2 开发。最先实施的内容必须是 WP1 的 Gate evaluation/reuse/cycle 合同，而不是继续调 Prompt，也不是先扩展更多检索源。
