# PaperAgent Re10 FIX — 5 个典型样例逐 case 审计

> 起草日: 2026-07-04  
> 范围: Re10 FIX SOP §3 (必跑典型样例) + §6 (交付物)  
> 来源数据: `tmp_re04_eval/re10_fix_typical_cases/{summary,run_manifest,reflection_stats}.json` + `traces/TYPICAL-0[1-5].json`  
> 配套: [PaperAgent_Re10_FIX_典型样例审计.csv](PaperAgent_Re10_FIX_典型样例审计.csv) (case-level, 5 cases)  
> 配套: [PaperAgent_Re10_FIX_SearchTrace_索引.md](PaperAgent_Re10_FIX_SearchTrace_索引.md) (trace 文件索引)  
> 配套: [PaperAgent_Re10_FIX_Validator输出.md](PaperAgent_Re10_FIX_Validator输出.md) (validator 原文)

## 0. 总览表 (5 case × evidence 列)

| case_id | 题目 | 路由 | re10_status | stop_reason | attempt | success | error | missing | new_cand | acc_cand | q_repair | u_repair | llm | evidence |
|---|---|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| TYPICAL-01 | 基于Unet的钢材裂缝分割 | industrial_inspection | no_new_signal | no_new_signal | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-02 | 基于三维成像的损伤智能检测 | 3d_imaging_inspection | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-03 | 基于多时相遥感数据的作物早期识别 | remote_sensing | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | **fail** |
| TYPICAL-04 | 基于大语言模型的医学问答答案可信度评估 | nlp_llm_medqa | blocked_tooling | blocked_tooling | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | **blocked_tooling** |
| TYPICAL-05 | X dynamic scene dataset | dataset_probe | no_new_signal | no_new_signal | 3 | 1 | 2 | 0 | 0 | 0 | 3 | 0 | 2 | **fail** |

**Totals**: attempt=25 success=11 error=14 missing=0 new_cand=0 acc_cand=0 q_repair=3 u_repair=0 llm=9

> 验算: 7+6+6+3+3 = 25 ✓; 6+2+2+0+1 = 11 ✓; 1+4+4+3+2 = 14 ✓; 11+14 = 25 ✓

证据状态分布: **pass=0, weak=0, blocked_tooling=1, fail=4**

## 1. TYPICAL-01 — 基于Unet的钢材裂缝分割

### Trace 还原 (round1 + round2)

- **round1 input_summary**: `must_search_n=2, seed_pool_n=0`  
  触发 3 个 action:
  - openalex `crack segmentation task benchmark` → success, 3 候选 (DeepCrack / MRI Cardiac / CrackFormer)  
    → 全部入 noise_candidates，与"钢材"无关
  - openalex `steel surface crack object benchmark` → success, 3 候选 (Deep Metallic / Review steel inspection / Additive manufacturing of steels)  
    → 全部入 noise_candidates（review 不是 dataset）
  - github `U-Net semantic segmentation github implementation` → no_results, 0 候选
- **round1 reflection**: dataset_gap / baseline_gap / repo_gap / noise_candidate / source_bias 共 5 条 diagnosis，全部 `next_action=repair_query` / `switch_source`
- **round2 input_summary**: `must_search_n=4`（reflection 把 must_search 翻倍）  
  触发 4 个 action:
  - openalex `基于Unet的钢材裂缝分割 dataset benchmark` → **no_results** (中文+多词空格被 API 拒)
  - openalex `基于Unet的钢材裂缝分割 baseline method` → **HTTP 429** (限流)
  - github `基于Unet的钢材裂缝分割 github implementation` → **no_results**
  - arxiv `基于Unet的钢材裂缝分割 narrow` → success, 3 候选但全是字面命中 "narrow" 的不相关 arxiv (Extreme Narrow Escape / Narrow Path RL / Narrow Optical Fe II)

### Evidence

| 列 | 值 |
|---|---|
| adapter_attempt_n | **7** (3 + 4) |
| adapter_success_n | **6** (openalex×2 + github no_results×1 + openalex no_results×1 + openalex 429×1 + arxiv×1) |
| adapter_error_n | **1** (openalex 429) |
| missing_client_n | 0 |
| new_candidates_n | 0 |
| accepted_candidates_n | 0 |
| query_repair_n | 0 |
| url_repair_n | 0 |
| llm_call_n | 2 |
| evidence_status | **fail** |

### 主要失败模式

1. round2 把"中文原句 + 关键词后缀"直接拼成 query 投给 openalex，openalex 不接受中文 token，返回 0 命中或触发限流。
2. arxiv 命中"narrow"是字面 substring 匹配 → **串题** (3 条 noise 都跟"钢/裂/UNet"无关)。这是 validator 还没拦的 substring 串题漏洞。
3. round1 选出的"DeepCrack / CrackFormer"虽然 paper 真实相关 (crack segmentation)，但**被 reflection 标 noise**而不是 good，accepted=0。

### 推荐修复

- round2 必须先做 **zh→en 翻译前移**：parse_topic 阶段必须产出 `query_atoms_en` (≤6 个英文词)，round2 不再用中文原句拼接。
- arxiv 命中如果跟 method+object term 都不沾边，应该 substring 二次过滤而不是全收。
- 修完后复跑此 case，`new_candidates_n ≥ 3` 才算 fix 成功。

## 2. TYPICAL-02 — 基于三维成像的损伤智能检测

### Trace 还原

- **round1**: openalex `damage detection task benchmark` / `structural damage object benchmark` → **HTTP 429 × 2**; github `U-Net semantic segmentation github implementation` → **no_results**。  
  reflection: dataset_gap / baseline_gap / repo_gap / source_bias, `next_action=switch_source`。
- **round2**: openalex `基于三维成像的损伤智能检测 dataset benchmark` / `基于三维成像的损伤智能检测 baseline method` → **HTTP 429 × 2**; github `基于三维成像的损伤智能检测 github implementation` → **no_results**。  
  reflection 重复 round1 的 4 条 diagnosis，但 round2 仍然把同一个中文原句拼给 openalex，等于**明知 429 还重发**。

### Evidence

| 列 | 值 |
|---|---|
| adapter_attempt_n | 6 |
| adapter_success_n | 2 (github no_results × 2, 算 successful empty return) |
| adapter_error_n | 4 (openalex 429 × 4) |
| missing_client_n | 0 |
| new_candidates_n | 0 |
| query_repair_n | 0 |
| url_repair_n | 0 |
| llm_call_n | 2 |
| evidence_status | **fail** |

### 主要失败模式

1. **openalex 429 限流**贯穿两轮，runner 既没切 crossref 也没做退避。Re10 FIX SOP §1.3 要求"OpenAlex 限流 (429) → 立刻切到 Crossref (circuit breaker)"，本轮没实现。
2. round2 没有用 round1 reflection 产出的 `next_round_focus` 调整 query，仍然发中文原句。
3. parse_topic 输出的 `domain_keywords.en[0]` 仍是 `U-Net` → github fallback 拿不到 3DGS / COLMAP / PointNet++ 任一 repo。

### 推荐修复

- runner 加 openalex 429 → crossref circuit breaker (重试 2 次后切换)。
- DomainScout 必须按"基于三维成像 + 损伤智能检测"拆出 `3D imaging / damage detection / structural inspection / point cloud` 而不是 `damage + object + benchmark` 这种三词硬拼。
- 接 arxiv `3D damage detection` / `point cloud defect` 兜底。

## 3. TYPICAL-03 — 基于多时相遥感数据的作物早期识别

### Trace 还原

- **round1**: openalex `early crop identification task benchmark` / `cropland object benchmark` → **HTTP 429 × 2**; github `U-Net semantic segmentation github implementation` → **no_results**。
- **round2**: openalex `基于多时相遥感数据的作物早期识别 dataset benchmark` / `... baseline method` → **HTTP 429 × 2**; github `... github implementation` → **no_results**。

与 TYPICAL-02 几乎**完全同形**，只是 query 字符串换了中文原句。

### Evidence

| 列 | 值 |
|---|---|
| adapter_attempt_n | 6 |
| adapter_success_n | 2 (github no_results × 2) |
| adapter_error_n | 4 (openalex 429 × 4) |
| missing_client_n | 0 |
| new_candidates_n | 0 |
| query_repair_n | 0 |
| url_repair_n | 0 |
| llm_call_n | 2 |
| evidence_status | **fail** |

### 主要失败模式

1. 与 TYPICAL-02 同源问题: openalex 429 + 中文原句拼接 + github fallback 错域 (`U-Net`)。
2. DomainScout 没识别出"多时相" → time series / temporal, 没识别出"作物早期识别" → early-season classification / crop type mapping; 也没识别出"Sentinel-2 / Landsat" 这类 RS 数据源 term。
3. round2 的 `cropland object benchmark` 和 `基于多时相遥感数据的作物早期识别 dataset benchmark` 完全是**乱拼**的英文 + 关键词后缀。

### 推荐修复

- 同 TYPICAL-02: openalex 429 → crossref circuit breaker。
- DomainScout prompt 必须强制拆 RS domain atoms: `multitemporal remote sensing / crop classification / Sentinel-2 / time series classification`。
- 失败一轮后必须**至少换一次 source**, 不允许把同一中文原句再扔给同一 adapter。

## 4. TYPICAL-04 — 基于大语言模型的医学问答答案可信度评估

### Trace 还原 (单 round 后 stop_reason=blocked_tooling)

- **round1**: openalex `answer trustworthiness evaluation task benchmark` / `LLM-generated medical answers object benchmark` → **HTTP 429 × 2**; github `U-Net semantic segmentation github implementation` → **HTTP 403** (rate limit)。
- 3 个 action **全部 status=error** → reflection 输出 5 条 diagnosis，但**前 3 条 evidence 字段是碎字符** (["三", "条", " ", "e", "x"] / ["f", "a", "l", "l", "b"] / ["g", "o", "o", "d", "_"]) — 显然 reflection LLM 退化成 character-level token 输出，**没有 JSON dict guard**。
- 之后无 round2 (refl 没有触发下一轮 focus)，直接 `stop_reason=blocked_tooling`。

### Evidence

| 列 | 值 |
|---|---|
| adapter_attempt_n | 3 |
| adapter_success_n | **0** ← 触发 H2 hard fail |
| adapter_error_n | 3 (openalex 429 × 2 + github 403 × 1) |
| missing_client_n | 0 |
| new_candidates_n | 0 |
| query_repair_n | 0 |
| url_repair_n | 0 |
| llm_call_n | 1 |
| evidence_status | **blocked_tooling** |

### 主要失败模式

1. **3 action 0 成功** — 这是 H2 唯一触发 case。runner / loop 必须能识别"全部 error" → `blocked_tooling` (✓ 已识别)，但 reflection prompt **没有 JSON 输出 guard** 导致 diagnosis 是碎字符。
2. github 403 是 unauthenticated rate limit, **必须接 GITHUB_TOKEN** 或者切 huggingface / openalex。
3. DomainScout 错把"医学问答答案可信度评估"路由成 fallback `U-Net semantic segmentation` (domain_keywords.en[0])，根本没去 NLP/LLM 路线。

### 推荐修复

- reflection prompt 必须加 JSON schema guard: diagnosis 必须是 `[{problem, evidence, root_cause, next_action}]`，并且 problem ∈ 固定枚举。碎字符时 fallback 到 heuristic_rules。
- runner 必须在 github 403 时切到 huggingface_search (`huggingface_search("medical QA trustworthiness benchmark")`)。
- DomainScout prompt 增加 domain_router: `nlp / llm / medqa` 路径，必须强制走 factuality / hallucination / MedQA / HealthSearchQA 类 term。

## 5. TYPICAL-05 — X dynamic scene dataset (占位符修复测试)

### Trace 还原

- **round1**: openalex `dynamic scene understanding task benchmark` / `dynamic scene images object benchmark` → **HTTP 429 × 2**; github `U-Net semantic segmentation github implementation` → **no_results**。
- **round2**: 触发 query_repair (3 次):
  - `X dynamic scene dataset dataset benchmark` → `needs_clarification` (error: `query contains X/{axis} placeholder; per SOP §4.4 hard rule never returned as repaired (has_brace=False, has_bare_x=True)`)
  - `X dynamic scene dataset baseline method` → 同上
  - `X dynamic scene dataset github implementation` → 同上
- repair **没真正修复**，原 query 仍出现在 trace `observations.query_placeholder_leaks` → 触发 H4 hard fail。
- round1 的 1 个 success 是 round1 后期 reflection 把 round1 早期一个 no_results action 标记 successful empty return? — 复跑真值 `success=1, error=2`，对应 round2 query_repair × 3 (算 successful empty return × 1) + 原始 action error × 2。但 validator 把 query_repair 归为 success 把 adapter 算成 3 attempt。

### Evidence

| 列 | 值 |
|---|---|
| adapter_attempt_n | 3 |
| adapter_success_n | 1 |
| adapter_error_n | 2 |
| missing_client_n | 0 |
| new_candidates_n | 0 |
| query_repair_n | **3** ← SOP §3 Case E 要求 |
| url_repair_n | 0 |
| llm_call_n | 2 |
| evidence_status | **fail** (因 H4 触发) |

### 主要失败模式

1. **query_repair 触发了但没真正修复**。SOP §4.4 硬规则是 `has_bare_x=True → needs_clarification never returned as repaired`，但 runner 还是把带 `X dynamic scene dataset` 前缀的 query 写进 executed_queries 和 query_placeholder_leaks。
2. DomainScout 接受题目 `X dynamic scene dataset` (X 占位符) **没在 parse_topic 阶段拦下**，一直传到 query_repair。
3. 修复后应该走 `needs_clarification → blocked_tooling` 而不是继续跑 round2。

### 推荐修复

- parse_topic (LLM parse 阶段) 必须 guard: 如果 title 含 `{axis}` 或前导独立 token `X` (regex `^\s*X\b`), 直接 emit `domain_route=needs_clarification` 不进 reflection loop。
- runner 的 query_repair 在 `has_bare_x=True` 时必须 abort round, 不再尝试 repair。
- H4 已经在 validator 拦下，本 case fail 是正确行为。

## 6. 5 case 共性失败 (跨 case 模式)

| 模式 | 触发 case | 频率 |
|---|---|---|
| openalex HTTP 429 (限流未退避) | TYPICAL-01 / 02 / 03 / 04 / 05 | **5/5** |
| round2 仍用中文原句拼接 query | TYPICAL-01 / 02 / 03 | **3/5** |
| DomainScout fallback 到 `U-Net semantic segmentation github implementation` | TYPICAL-01 / 02 / 03 / 04 / 05 | **5/5** (每个 round1 都 fallback 到这同一个错域 query) |
| reflection `next_round_focus` 没真正改变下一轮 query 形态 | TYPICAL-01 / 02 / 03 / 05 | **4/5** |
| 全部 action error 时 reflection 退化成碎字符 | TYPICAL-04 | **1/5** |
| query_repair 触发但 query 仍泄漏到 trace | TYPICAL-05 | **1/5** |

> 关键观察: **`U-Net semantic segmentation github implementation` 这个 fallback query 是 round1 input_summary 模板硬编码** (5 个 case 完全相同的 why: `fallback repo probe from domain_keywords.en[0]`)，DomainScout 永远不拆解出 case-specific repo term。

## 7. 总结

5 个典型样例 **0/5 通过**, 1 个被识别为 `blocked_tooling`, 4 个被识别为 `fail`。  
触发 3 个 hard-fail gate (H2 / H4 / H9), 见 [Validator输出.md](PaperAgent_Re10_FIX_Validator输出.md)。

下一步必修项见 [PaperAgent_Re10_FIX_完工报告.md §4](PaperAgent_Re10_FIX_完工报告.md)。