# PaperAgent Re10 FIX — 完工报告

> 起草日: 2026-07-04  
> 范围: `PaperAgent_Re10_FIX_评分器与Agent接线修复_SOP.md` §6 全部交付物  
> 运行根目录: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\`  
> 配套: [典型样例审计.csv](PaperAgent_Re10_FIX_典型样例审计.csv) / [典型样例审计.md](PaperAgent_Re10_FIX_典型样例审计.md) / [SearchTrace_索引.md](PaperAgent_Re10_FIX_SearchTrace_索引.md) / [Validator输出.md](PaperAgent_Re10_FIX_Validator输出.md)

## 结论 (一行)

**Re10 FIX 本次未通过 validator 硬门槛（3 hard fail），需继续修复。**  
5 个典型样例 pass=0, weak=0, blocked_tooling=1, fail=4 — SOP §4 最小通过条件全部不满足。

---

## §0. 接线修复结果 (Step 1 / Step 2 / Step 3 落地情况)

### 0.1 runner 端 retrieval client 接线 (SOP Step 1)

按 SOP §5 Step 1 要求, `run_balanced40_reflection_re10.py` 必须返回长 key (`arxiv_search` / `openalex_search` / `crossref_search` / `github_search` / `huggingface_search`)。  

本轮 5 个 case 的 trace `tool_stats.missing_client_n` **全部 = 0** (CSV 列 missing_client_n), 即 runner 已经正确返回长 key, loop 端能通过 `TOOL_CLIENT_KEYS` 找到 adapter 函数。SOP §1.1 描述的"missing client openalex_search"问题**已经修复**。

```text
H1 missing_client_n == 0  →  PASS (5/5 case 都满足)
```

### 0.2 stop_reason 修复 (SOP Step 2)

按 SOP §5 Step 2 要求, `_decide_stop()` 必须先判断工具故障, 再判断 `no_new_signal`, 且 `blocked_tooling` 必须写入 trace。

本轮 stop_reason 分布:

- `no_new_signal`: 4 case (TYPICAL-01 / 02 / 03 / 05)
- `blocked_tooling`: 1 case (TYPICAL-04)

TYPICAL-04 的 3 个 action 全部 status=error 且 reflection 输出碎字符, loop 正确识别 `blocked_tooling` 而不是误判为 `no_new_signal`。SOP §1.2 的"工具错误归类为 no_new_signal"问题**已经修复**。

### 0.3 validator 修复 (SOP Step 3)

按 SOP §5 Step 3 要求, validator 必须:

- 删除"repair gate 永远 true"的逻辑 ✓
- 任何 Trace 中出现 `missing client` 即 hard fail ✓ (H1)
- `adapter_attempt_n > 0` 但 `adapter_success_n == 0` 即 hard fail ✓ (H2, 触发于 TYPICAL-04)
- `pass/weak/fail/blocked` 由 evidence 推导 ✓ (H9, pass+weak>0 必须成立)

`validate_re10_reflection_search.py` 的 3 个 hard-fail gate (H2 / H4 / H9) 本轮**真实触发**, 退出码 = 1。SOP §1.3 描述的"评分器永远通过"问题**已经修复** — validator 不再是橡皮图章。

### 0.4 接线修复的"通过"是分层的

| 项 | 修复前 (Re10) | 修复后 (Re10 FIX) |
|---|---|---|
| missing client | 40/40 case 命中 | 0/5 case 命中 |
| stop_reason 被 `no_new_signal` 粉饰 | 普遍 | 已区分 blocked_tooling |
| validator 永远 PASS | 40/40 PASS (假阳性) | 5/5 触发 hard fail (真阴性) |
| Trace schema 含 evidence 列 | 部分 | 全部含 attempt/success/error/missing/new/acc/q_repair/u_repair/llm |

**但**: 接线修复 ≠ 搜索修复。runner 接上了、validator 能拦了, **但 5 个 case 一个真候选都没拿到** (`new_candidates_n=0/0/0/0/0`)。Re10 FIX 解决了"假阳性"问题, 没解决"零结果"问题。

---

## §1. Validator 现状 (复跑真值)

### 1.1 复跑命令

```bash
cd /g/PaperAgent && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
    apps/api/scripts/validate_re10_reflection_search.py \
    --re10-dir tmp_re04_eval/re10_fix_typical_cases \
    --allow-no-llm --skip-baseline-gates
```

退出码: **1 (FAIL)**。完整原文见 [Validator输出.md](PaperAgent_Re10_FIX_Validator输出.md)。

### 1.2 per-case 复跑表

| case_id | re10_status | stop_reason | attempt | success | error | missing | new_cand | acc_cand | q_repair | u_repair | llm | evidence_status |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| TYPICAL-01 | no_new_signal | no_new_signal | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-02 | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-03 | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-04 | blocked_tooling | blocked_tooling | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | **blocked_tooling** |
| TYPICAL-05 | no_new_signal | no_new_signal | 3 | 1 | 2 | 0 | 0 | 0 | **3** | 0 | 2 | **fail** |

**Totals**: attempt=25 success=11 error=14 missing=0 new_cand=0 acc_cand=0 q_repair=3 u_repair=0 llm=9  
**by_status**: `{'fail': 4, 'blocked_tooling': 1}` (pass=0, weak=0)

### 1.3 hard-fail gates (8 个)

| Gate | 状态 | 触发 / 说明 |
|---|:---:|---|
| H1 missing_client_n == 0 | PASS | 5/5 case missing=0 |
| H2 adapter_success_n > 0 when attempt > 0 | **FAIL** | `zero_success_cases=['TYPICAL-04']` |
| H3 llm_call_n 检查 | SKIP | `--allow-no-llm` 启用; 本次 llm=9 |
| H4 无 query_placeholder_leaks | **FAIL** | `leak_cases=['TYPICAL-05']` (3 条 X 占位符) |
| H5 url_repair_n > 0 when empty_url > 0 | PASS | empty_url_n=0 vacuously PASS |
| H6 trace_coverage.with_trace == n_total | PASS | 5/5 有 trace |
| H7 Re08 seeds preserved | SKIP | `--skip-baseline-gates` 启用 |
| H8 Re09 regression cases | SKIP | `--skip-baseline-gates` 启用 |
| H9 pass+weak (evidence-driven) > 0 | **FAIL** | pass=0 weak=0 blocked=1 fail=4 |

**3 hard-fail**: H2, H4, H9。

### 1.4 与 task prompt 占位数据的差异 (以复跑真值为准)

| 字段 | task prompt 占位 | 复跑真值 | 差异原因 |
|---|---|---|---|
| TYPICAL-01 attempt/success/error | 6/4/2 | **7/6/1** | round2 加了 1 个 arxiv action |
| TYPICAL-05 evidence_status | weak | **fail** | query_placeholder_leaks 触发 H4 → 降级 |

其余 3 个 case (TYPICAL-02 / 03 / 04) 数字一致。

---

## §2. 5 个典型样例逐 case 分析

详细每个 case 的 trace 还原见 [典型样例审计.md §1-§5](PaperAgent_Re10_FIX_典型样例审计.md)。本节给一句话总结 + evidence 表。

### 2.1 TYPICAL-01: 基于Unet的钢材裂缝分割 — **fail**

- **一句话**: round1 拿到 6 个 candidate 都是 crack segmentation 真实文献, 但被 reflection 误标 `noise_candidate`; round2 把中文原句拼接 + `narrow` 字面命中 → 串题到 arxiv 上的 Extreme Narrow Escape / Narrow Path RL / Narrow Fe II 3 篇天文/RL 论文。
- **主要 failure mode**: round2 中文原句 + arxiv 字面 substring 串题。
- **Evidence**: 7/6/1/0/0/0/0/0/2 → **fail**

### 2.2 TYPICAL-02: 基于三维成像的损伤智能检测 — **fail**

- **一句话**: 两轮 openalex 全部 HTTP 429 (4 次), 没有 circuit breaker 切 crossref; DomainScout 错把 `U-Net` 当 repo fallback。
- **主要 failure mode**: openalex 限流 + 错域 fallback。
- **Evidence**: 6/2/4/0/0/0/0/0/2 → **fail**

### 2.3 TYPICAL-03: 基于多时相遥感数据的作物早期识别 — **fail**

- **一句话**: 与 TYPICAL-02 完全同形 (同 runner bug), DomainScout 没识别 RS / 时序 / 作物分类的 domain atoms。
- **主要 failure mode**: openalex 限流 + DomainScout 没拆 RS 域。
- **Evidence**: 6/2/4/0/0/0/0/0/2 → **fail**

### 2.4 TYPICAL-04: 基于大语言模型的医学问答答案可信度评估 — **blocked_tooling**

- **一句话**: 3 action 全部 error (openalex 429 × 2 + github 403 × 1), reflection LLM 退化成碎字符输出, runner 立即 stop。这是**唯一触发 H2**的 case。
- **主要 failure mode**: 全部 action error + reflection prompt 无 JSON guard + github 403 unauthenticated。
- **Evidence**: 3/0/3/0/0/0/0/0/1 → **blocked_tooling**

### 2.5 TYPICAL-05: X dynamic scene dataset — **fail** (H4 触发)

- **一句话**: round2 query_repair 触发 3 次全部返回 `needs_clarification` (因 `has_bare_x=True`), 但**修复后的 query 仍泄漏**到 trace.observations.query_placeholder_leaks, 触发 H4 hard fail。
- **主要 failure mode**: parse_topic 没拦 X 占位符, runner 把未修复 query 写进 executed_queries。
- **Evidence**: 3/1/2/0/0/0/**3**/0/2 → **fail**

---

## §3. 不通过原因分析 (3 hard fail)

### 3.1 H2 fail: TYPICAL-04 全部 action 0 成功

**根因**: 

1. **DomainScout 错域**: 把"基于 LLM 的医学问答可信度评估"路由成 fallback `U-Net semantic segmentation github implementation` (5 个 case round1 全部相同 query)。SOP §5 必跑 Case D 要求 NLP/LLM 路线, runner 没做到。
2. **openalex 429**: 不带 retry / 不切 crossref, 4 个 case 都重复触发。
3. **github 403**: unauthenticated rate limit, 没接 `GITHUB_TOKEN`, 也没切 huggingface_search。
4. **reflection prompt 无 JSON guard**: LLM 退化成 character-level 输出 (`["三", "条", " ", "e", "x"]`), 不能形成可解析的 diagnosis dict。

**位置**: 

- `apps/api/scripts/run_balanced40_reflection_re10.py` — DomainScout prompt + adapter fallback
- `apps/api/app/services/agents/search_reflection_loop.py` — reflection prompt + circuit breaker 缺失

### 3.2 H4 fail: TYPICAL-05 query_placeholder_leaks

**根因**: 

1. **parse_topic 阶段未拦占位符**: 题目 `X dynamic scene dataset` 中的前导独立 token `X` (regex `^\s*X\b` 或 `{axis}` 占位符) 在 `parse_topic` LLM 解析时被放过, 一路传到 query_repair。
2. **query_repair 返回 needs_clarification 后未 abort**: SOP §4.4 硬规则要求 `has_bare_x=True` 时 `never returned as repaired`, 但 runner 把原 query 仍写进 `executed_queries` 和 `observations.query_placeholder_leaks`。

**位置**: 

- `apps/api/app/services/agents/prompts/parse_topic.py` — 占位符 guard 缺失
- `apps/api/app/services/agents/search_reflection_loop.py` — `_execute_query()` 在 needs_clarification 后未 raise

### 3.3 H9 fail: 0 pass + 0 weak

**根因**: 

5 case 全部没有 `new_candidates_n > 0` (5/5 = 0 new candidates), accepted_candidates_n 也全部 = 0。**没有任何 case 进入 7-bucket 收口阶段** (`final.paper_n / baseline_n / parallel_n / dataset_n / repo_n` 全部 = 0)。

这是 §3.1 + §3.2 综合症状: 

- DomainScout 错域 → adapter 拿不到相关候选
- openalex 限流 → adapter 拿到 429 → 没有候选
- 中文原句拼接 → adapter 拿不到相关候选
- arxiv 字面 substring 串题 → 候选被 reflection 标 noise

5 case 共性: **adapter 调用了, 但工具链路没有返回任何与题目相关的真候选**。

---

## §4. 下一步必须修什么

按 SOP §4 最小通过条件倒推:

| SOP §4 条件 | 当前 | 必修项 |
|---|---|---|
| `missing_client_n == 0` | ✓ PASS (5/5) | 无需修 |
| `adapter_attempt_n > 0` | ✓ PASS (5/5) | 无需修 |
| `adapter_error_n / adapter_attempt_n < 0.05` | ✗ 14/25 = 0.56 | 修 openalex 429 退避 / github 403 token / crossref circuit breaker |
| 5 case 中 ≥3 有 `new_candidates_n > 0` | ✗ 0/5 | 修 DomainScout parse_topic (错域 fallback + 中文原句拼接) |
| 5 case 中 ≥3 有 `accepted_candidates_n > 0` | ✗ 0/5 | 修 reflection good_candidates 判据 (TYPICAL-01 的 crack segmentation 真实文献不该被标 noise) |
| Case E 必须 `query_repair_n > 0` | ✓ PASS (TYPICAL-05 = 3) | 但 query 仍泄漏, 修 H4 |
| `url_repair_pending` / `url_repaired` 标记 | n/a (无 empty URL) | 暂无需修 |
| `no_new_signal` 不当工具失败别名 | ✓ (TYPICAL-04 已正确分类 blocked_tooling) | 无需修 |

### 4.1 P0 (修不完 Re11 跑不起来)

1. **DomainScout parse_topic 重写** (`apps/api/app/services/agents/prompts/parse_topic.py`)
   - 强制产出 `domain_route` ∈ {cv_segmentation, 3d_reconstruction, remote_sensing_timeseries, nlp_llm_medqa, ...} 固定枚举
   - 强制产出 `query_atoms_en` (≤ 6 英文 atom) 和 `repo_probe_queries` (≤ 3 真实 repo query, **禁止 fallback 到 `U-Net semantic segmentation` 这种通用 query**)
   - 占位符 guard: 输入含 `{axis}` / `^\s*X\b` 时直接 emit `domain_route=needs_clarification`
   - 输出必须可 JSON 解析, schema guard

2. **openalex 429 circuit breaker** (`apps/api/scripts/run_balanced40_reflection_re10.py`)
   - openalex 连续 2 次 429 → 切 crossref
   - 加指数退避 (0.5s / 1s / 2s)
   - 加 user-agent 标识避免被识别为 bot

3. **github 403 / 限流兜底** (`run_balanced40_reflection_re10.py` 或 adapter 层)
   - 接 `GITHUB_TOKEN` from `.env`
   - 403 时切 huggingface_search (已有 adapter, runner 没接)

4. **reflection prompt JSON guard** (`apps/api/app/services/agents/prompts/...`)
   - diagnosis 强制 JSON Schema, problem ∈ 固定枚举
   - 解析失败时 fallback 到 heuristic_rules 不重试 LLM

### 4.2 P1 (修了能显著提高 accept rate)

5. **zh→en 翻译前移**: parse_topic 必须产 `query_atoms_en`, round2 不再投中文原句给 openalex/github。
6. **arxiv 字面 substring 串题 guard**: round2 arxiv 命中如果跟 method+object term 都不沾边, substring 二次过滤。
7. **reflection good_candidates 判据**: TYPICAL-01 round1 的 DeepCrack / CrackFormer 是 crack segmentation 真实文献, 不应该被标 noise — 需要放宽 noise 判据 (只剔除**与 method+object term 都不沾边**的)。

### 4.3 P2 (后续 Re11 才用)

8. retry LLM 失败 → simulated synthesis fallback
9. 7-bucket 收口: `final.paper_n > 0` 才算 reflection 闭环成功
10. 抽样 10 → Balanced40 全量扩展

### 4.4 验收门槛 (Re10 FIX-2 / Re11)

修完上述 P0 后, 必须满足:

```text
- 5 case 全部: missing_client_n == 0
- 5 case 中 ≥4: adapter_success_n > 0
- 5 case 中 ≥4: new_candidates_n > 0
- 5 case 中 ≥3: accepted_candidates_n > 0
- TYPICAL-04 (Case D): 走 nlp_llm 路线, 至少 1 个 MedQA / factuality 真实候选
- TYPICAL-05 (Case E): query_placeholder_leaks == 0, repair 后 stop_reason=blocked_tooling
- validator H2 / H4 / H9 全部 PASS
```

不满足 → 不进入 Re11, 继续修。

---

## §5. 一句话总结 (给项目协作)

Re10 FIX **解决了"假阳性"问题** (missing client / 评分器永远 PASS / stop_reason 被粉饰, 共 3 项全部修复), 但**没有解决"零结果"问题** (5 case 全部 `new_candidates_n=0`, accepted=0)。  
下一轮 (Re10 FIX-2 或直接 Re11) 必须先修 DomainScout parse_topic + openalex 429 退避 + github token + 占位符 guard 这 4 个 P0 项, 否则 validator 永远是 3 hard fail。

---

## §6. 交付物清单 (SOP §6 全部生成)

| 文件 | 大小 | 状态 |
|---|---:|---|
| `Plan/PaperAgent_Re10_FIX_完工报告.md` | (本文件) | ✓ |
| `Plan/PaperAgent_Re10_FIX_典型样例审计.csv` | 2,086 B | ✓ (5 case × 18 列) |
| `Plan/PaperAgent_Re10_FIX_典型样例审计.md` | 14,113 B | ✓ (5 case 逐 case) |
| `Plan/PaperAgent_Re10_FIX_SearchTrace_索引.md` | 8,142 B | ✓ (5 trace 索引 + 共性表) |
| `Plan/PaperAgent_Re10_FIX_Validator输出.md` | 5,152 B | ✓ (validator 原文 + 偏差说明) |

可选交付物 (`Re10_FIX_抽样10审计.*`) SOP §6 标注为可选, 本轮**不生成** — 因为 5 典型样例都没过, 抽样 10 没意义, 等 P0 修完再扩。

---

## §7. 后续动作

- **立刻**: 把 §4.1 P0 的 4 项列为下一个 session 的 first-class ticket, 不混 Re11 范围。
- **同步 `/docs`**: SOP §8 提示本轮涉及 Agent 状态、检索链路、评分器、Trace schema 和验收口径, 修完后由用户决定是否同步 `/docs`。
- **不进入 Re11**: 本轮通过条件 (SOP §4) 不满足, 不允许扩到 Balanced40 抽样或全量。