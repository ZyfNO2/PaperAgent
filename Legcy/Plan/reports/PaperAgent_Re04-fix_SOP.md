# PaperAgent Re04-fix SOP

> 起草日：2026-07-02
> 前置文档：
> - `Plan\PaperAgent_Re04_审计细节_保留与剔除.md`（Smoke 5 raw dump 审计）
> - `Plan\PaperAgent_Re04-fix_代码修复方案.md`（初版修复草案，本 SOP 取代其执行条款）
> - `Plan\PaperAgent_Re04_完工报告.md`
> 参考实现（必读，已核实路径真实存在）：
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\search.py:104-231`
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\semantic_scholar.py:40-69`
> - `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-paper\agents\literature_strategist_agent.md`（§Search Strategy Design / §Chinese-English Literature Search Difference Handling 第 516-530 行）

---

## 0. 目标与不做的事

**目标**：修复 Re04 Online Smoke 5 暴露的 6 个代码级缺陷 + 1 个预算缺陷，使 5 个 case 中至少 015/016/027 升到 weak 且降级路径可追溯，018/024 不再因预算断链。

**不做**：
- 不改 LLM ER 的 prompt 文本（守 S66v「不泄题」）
- 不改 `crossref_search.py` / `arxiv_client.py` 等适配器
- 不新增 `*_score` 字段、不新增静态 baseline/dataset 目录（S66v）
- 不跑 balanced 40（那是验收后才做的）

---

## 1. 诊断：6 + 1 个缺陷（全部已对源码核实）

Smoke 5 的 1 weak + 4 fail 由三条独立失败路径产生：

```
Path A（纯中文题 — Case 027）
  LLM parse 失败 → _heuristic_parse → method_terms=[]
  → query_matrix "if method:" 跳过 → baseline_family=[]            [缺陷1]
  → adapter 英文 query=空 → crossref 靠 fb_atom（中文）返 8 篇
  → result_expander 中文 token 拼 garbled query → S2 返 JATS 噪声   [缺陷4]
  → seed_relevance method_terms=[] 全拒 seed → citation_expand=0   [缺陷2]
  → LLM ER 中英混合 pool → JSON parse 连败 → 16/16 heuristic        [缺陷3]
  → synthesis 双闸门 status!=core 全进 reference → baseline=0      [缺陷6]
  → eval 硬判 fail，无降级                                          [缺陷7=降级缺失]

Path B（混合题 — Case 016）
  query_matrix baseline=["visual SLAM classic"] → "classic" 无效   [缺陷1]
  → crossref 只返 VO 论文
  → seed_relevance "visual SLAM" 要求 visual+slam 都在 → 缺 slam → miss [缺陷2]
  → LLM ER 21/21 全 candidate（不愿给 core）
  → 双闸门 → 21 条全 reference，baseline=0                          [缺陷6]
  → eval 硬判 fail                                                  [缺陷7]

Path C（LLM 预算断 — Case 018/024）
  12-call/case 预算耗尽 → 任何 adapter 都没发 → pool=0              [缺陷5=预算]
```

| # | 文件:行 | 缺陷 | 影响 case | 类型 |
|---|---|---|---|---|
| 1 | `query_matrix.py:136-139` | `if method:` 在 method_terms=[] 时 baseline query 零产出 | 027/016 | 结构 bug |
| 2 | `seed_relevance.py:55-60` | `all(w in haystack_tokens)` 全词 AND，多词 term 缺一即 miss | 016/027 | 阈值设计 |
| 3 | `evidence_review.py:207-244` | 中英混合 pool → JSON parse 两次全败 → 全量 heuristic；中文 prompt `RE04_EVIDENCE_REVIEW_SYSTEM`（synthesize.py:265）已存在但未导入 | 027 | 降级缺失 |
| 4 | `result_expander.py:40-104` | `_TOKEN_RE` 含中文 → garbled query 喂英文 API | 027 | 滤波缺失 |
| 5 | LLM 预算 | 12-call/case 上限 → 018/024 整链断 | 018/024 | 预算配置 |
| 6 | `research_agent.py:2488-2489` | baseline 桶双闸门：`status==core AND relation==baseline` 才进；candidate+baseline 被丢进 reference | 016/027 | 结构严苛 |
| 7 | `re04_entry.py:344-357` + `eval/__init__.py:192` | 无跨轮根因链；baseline_n<1 二值硬判 fail，无降级 | 全部 | 可观测+降级 |

---

## 2. 修复 1：query_matrix baseline_family 四层退路

### 2.1 位置
`apps/api/app/services/agents/query_matrix.py:136-139`

### 2.2 改动
- 第一优先：`method × task` 组合（最精确）
- 第二退路：仅 method_terms
- 第三退路：仅 task_terms（针对 method=[] 的中文题）
- 最终退路：fb_atom（用户原文，**显式降级标记**）
- 删除 `"classic"` 后缀（AutoResearchClaw `search.py` 的 query 不加语义标签，直接术语搜——已核实）

### 2.3 降级标记
返回 dict 新增 `baseline_fallback_reason`：
- `null`（method+task 都有，无降级）
- `no_task_terms_use_method_only`
- `no_method_terms_use_task_only`
- `no_lexical_terms_use_raw_topic_fallback`（最末退路，必须标记）

### 2.4 验证
| case | method | task | fb_atom | 修复后 baseline | fallback_reason |
|------|--------|------|---------|-----------------|-----------------|
| 027 | [] | [] | "基于YOLOv5..." | ["基于YOLOv5..."] | `no_lexical_terms_use_raw_topic_fallback` |
| 016 | ["visual SLAM"] | ["visual odometry"] | any | ["visual SLAM visual odometry"] | `null` |

### 2.5 参考依据
AutoResearchClaw `search.py:113-134` `search_papers()` 的 query 是纯术语直搜，不加 baseline/survey/classic 后缀。本修复借鉴其「术语直搜」原则。

---

## 3. 修复 2：seed_relevance 阈值匹配

### 3.1 位置
`apps/api/app/services/agents/seed_relevance.py:47-61`

### 3.2 改动
`all(w in haystack_tokens)` → `len(matched_words) >= ceil(len(words)/2)`（半数词命中即匹配）。

### 3.3 降级标记
`evaluate_seed()` 返回的 `_debug` 新增 `matched_mode: "threshold"`；凡触发阈值匹配的，`matched_axis` 末尾追加 `_threshold` 后缀。

### 3.4 验证
| seed title | term | words | 修复前 | 修复后 |
|---|---|---|---|---|
| Visual Odometry Based on CNN | "visual SLAM" | {visual,slam} | miss（缺 slam） | **hit**（threshold=1，命中 1/2） |
| Comparative Analysis of Monocular VO | "semantic mapping" | {semantic,mapping} | miss | miss（0/2） |

### 3.5 参考依据
academic-research-skills `literature_strategist_agent.md` §Search Strategy Design 使用布尔 OR 组合 + 同义词，不依赖单词全匹配。AutoResearchClaw `_deduplicate()` 用 DOI→arXiv→title 三级 OR 回退。multi-word 变 OR-like 提高 recall，与二者一致。

---

## 4. 修复 3：ER 中文 prompt 接线 + 三次兜底

### 4.1 位置
`apps/api/app/services/agents/evidence_review.py:31, 207-244`

### 4.2 现状关键事实
- 中文 prompt `RE04_EVIDENCE_REVIEW_SYSTEM` **已存在**于 `prompts/synthesize.py:265`
- 但 `evidence_review.py:31` 只 import 了英文版 `EVIDENCE_REVIEW_SYSTEM`，中文版从未被调用
- 这是「资产现成却没接」，不是要新写 prompt

### 4.3 改动
**A. 中文检测函数** `_has_majority_chinese(chunk)`：候选 title >50% 含中文 → True

**B. 接线**：`audit_candidates` 检测到中文占多数 → chunk_size 减半 + 切换到 `RE04_EVIDENCE_REVIEW_SYSTEM`

**C. 第三次兜底**：2 次重试全败后，若 chunk>3，逐候选评（chunk_size=1，max_tokens=6000），成功替换全量 heuristic

**D. 降级标记**（`_heuristic_review_for` 增 `degraded_from` 参数）：
| 场景 | reason 内标签 |
|---|---|
| per-candidate 兜底成功 | `[degraded: chunk_fallback_per_candidate]` |
| per-candidate 兜底也败 | `[degraded: chunk_fallback_per_candidate_failed]` |
| 无中文检测（原逻辑） | `[llm_blocker: evidence_review_parse_failed]`（保持不变） |

### 4.4 参考依据
academic-research-skills `literature_strategist_agent.md` §Chinese-English（第 516-530 行）明确要求中英文分开检索和评估。本修复「中文候选 → 中文 prompt + 更小 chunk」与此一致：不改 LLM，只让 LLM 接触更少更清晰的上下文。

---

## 5. 修复 4：result_expander 中文乱码滤波

### 5.1 位置
`apps/api/app/services/agents/result_expander.py:40-104`

### 5.2 改动
**A.** 新增 `_is_chinese_dominated(text, threshold=0.5)` + `_filter_english_tokens()`

**B.** `expand_from_round1` 内：token 计数前跳过中文 dominated token；query 构建前再过滤一次

**C.** 全中文（filter 后 out 为空）→ 返回 `({}, {"degraded_reason": "all_queries_chinese_garbled_skipped"})`，`re04_entry` 读此标记写入 `round_delta["R2_dynamic_expansion"]["degraded_reason"]`

### 5.3 参考依据
AutoResearchClaw `arxiv_client.py` / `openalex_client.py` 的 query 全英文，整个 literature 模块不接受中文 query。本修复「检测到 garbled 就 skip，不尝试发中文给英文 API」与之方向一致。

---

## 6. 修复 5：LLM 预算取消上限（Case 018/024）

### 6.1 位置
LLM 调用预算配置（12-call/case 上限）

### 6.2 改动
取消 per-case LLM call 上限。CLAUDE.md 已明确「MiniMax 配额随便烧」。预算不再作为失败根因。

### 6.3 边界
- 不取消单次调用的 timeout / max_tokens（那两个是稳定性约束，不是预算）
- 不取消 circuit breaker（AutoResearchClaw `semantic_scholar.py:46-48` 的三态 CB 是限流保护，保留）

### 6.4 验证
Case 018/024 重跑后 round_delta 的 `R1_family_dispatch.per_adapter` 至少 2 个 adapter 非零，pool 非空。

---

## 7. 修复 6：baseline 双闸门降级（核心）

### 7.1 位置
`apps/api/app/services/agents/research_agent.py:2488-2496`

### 7.2 现状严苛点
```python
if r.status == "core":
    (paper_groups["baseline"] if r.relation_to_topic == "baseline"
     else paper_groups["parallel"]).append(entry)
elif r.status == "candidate":
    paper_groups["reference"].append(entry)   # ← candidate+baseline 被丢这里
```
候选必须**同时** `status==core AND relation==baseline` 才进 baseline 桶。LLM 不愿给 core 时，再像 baseline 的论文也进不了 baseline 桶。

### 7.3 改动：有标记降级（满足「必须标记为自己找不到降级」硬要求）

在 `research_agent.py:2496` baseline_ids 计算后、return 前插入：

```python
if not paper_groups["baseline"]:
    promoted = []
    src_bucket = ""
    if paper_groups["parallel"]:
        promoted = paper_groups["parallel"][:2]
        src_bucket = "parallel"
    elif paper_groups["reference"]:
        promoted = paper_groups["reference"][:1]
        src_bucket = "reference"
    for p in promoted:
        p["degraded_role"] = f"self_cannot_find_baseline_promoted_from_{src_bucket}"
        p["degraded_reason"] = "system_cannot_locate_true_baseline_do_not_treat_as_reproducible"
        paper_groups["baseline"].append(p)
    if promoted:
        paper_groups["_baseline_degraded"] = True
        paper_groups["_baseline_degraded_marker"] = "self_cannot_find_baseline_degradation"
        paper_groups["_baseline_degraded_source"] = src_bucket
```

### 7.4 降级标记三层落点（禁止只藏 debug）

| 层 | 字段 | 值 |
|---|---|---|
| 候选级 | `entry["degraded_role"]` | `self_cannot_find_baseline_promoted_from_parallel/reference` |
| 候选级 | `entry["degraded_reason"]` | `system_cannot_locate_true_baseline_do_not_treat_as_reproducible` |
| synthesis 级 | `paper_groups["_baseline_degraded_marker"]` | `self_cannot_find_baseline_degradation` |
| 全局链 | `degradation_chain` 追加 | `pool:zero_baseline_self_cannot_find_degraded_to_{parallel/reference}` |

### 7.5 eval 配套（否则降级了仍 fail = 白降）

`apps/api/app/services/agents/eval/__init__.py:183-199` 改：

```python
baseline_entries = paper_groups.get("baseline") or []
baseline_n = len(baseline_entries)
baseline_degraded = any("degraded_role" in e for e in baseline_entries)

if baseline_n < 1:
    evidence_gap_reasons.append(f"baseline_n={baseline_n} < 1")
# ...
if has_noise:
    status = "fail"
elif baseline_n < 1:
    status = "fail"
elif baseline_degraded:
    status = "weak"  # 降级 baseline 允许升到 weak，但不许 pass
    evidence_gap_reasons.append("baseline_is_self_cannot_find_degradation")
elif paper_n >= 8 and ...:
    status = "pass"
elif paper_n >= 4 and baseline_n >= 1:
    status = "weak"
```

`write_markdown_report` 的 reason 列必须显示 `baseline_is_self_cannot_find_degradation` 字样。

### 7.6 不降级的情况（边界）
- baseline + parallel + reference 全空 → 保持 fail（无东西可提升，降级无意义）
- 整链断（018/024 预算修前）→ 不在本降级范围

### 7.7 优先级（Q3 决议）
parallel 优先提升（比 reference 更近 baseline）→ parallel 空才退 reference。Case 016 的 21 条全 reference → 提 1 条 reference 作降级 baseline。

---

## 8. 修复 7：degradation_chain 全局可追溯链

### 8.1 位置
`apps/api/app/services/agents/re04_entry.py:344-357`（返回 dict 处）

### 8.2 改动
新增 `_build_degradation_chain()`，聚合 7 个失败点：
1. parse 降级（`parsed._heuristic`）
2. query_matrix 降级（`baseline_fallback_reason` / zero_baseline_queries / zero_dataset_queries）
3. R1 全 adapter 空
4. R2 降级（`r2_delta.degraded_reason`）
5. citation_expand 全 seed 拒
6. ER 降级（blocked / degraded 计数）
7. pool zero baseline（含 7.3 的 self_cannot_find 标记）

返回 dict 新增 `"degradation_chain": chain`。

### 8.3 预期 chain
- Case 027：`["parse:heuristic_fallback", "query_matrix:baseline_no_lexical_terms_use_raw_topic_fallback", "query_matrix:zero_dataset_queries", "r2:all_queries_chinese_garbled_skipped", "evidence_review:all_heuristic_blocked", "pool:zero_baseline_self_cannot_find_degraded_to_reference"]`
- Case 016：`["citation_expand:all_seeds_rejected", "pool:zero_baseline_self_cannot_find_degraded_to_reference"]`

### 8.4 参考依据
academic-research-skills「IRON RULE: every claim needs citation」要求来源可追溯。AutoResearchClaw circuit breaker 在源失败后转移并记录。本 chain 是输出侧的对等物。

---

## 9. 执行边界

### 9.1 范围内
- ✅ 修复 1-7 共 7 处代码改动
- ✅ 降级标记三层落地 + eval 配套识别
- ✅ 中文 prompt 接线（现成资产，改 import + 分派）
- ✅ 新增测试覆盖降级标记断言
- ✅ 每修复一个独立 commit，可回滚

### 9.2 范围外（禁止）
- ❌ 不改 ER 的 prompt 文本内容
- ❌ 不改适配器代码
- ❌ 不新增 `*_score` / 静态目录
- ❌ 不跑 balanced 40

### 9.3 禁止偷懒清单

| 禁止 | 为什么 |
|---|---|
| 降级时 reference rename 成 baseline 不打标 | 违反「必须自标记」硬要求 |
| 降级标记只写 logger 不写返回 dict | 审计看不到 = 没标 |
| eval 不改，降级后仍 fail | 降级白做 |
| `seed_relevance` 改 `always eligible` | 引入离题种子噪声 |
| ER 中文修复改「中文候选全 pass」 | 违反 S66v 不泄题 |
| `if "YOLOv5" in title: keep` 硬白名单 | 违反 S66v |
| 一次改完不逐个 commit | 违反「可回滚」 |
| 降级标记藏在 `_debug` 子字段不写文档 | 违反「自标记」要求 |
| budget 取消连 timeout/circuit breaker 一起删 | 那俩是稳定性约束不是预算 |

---

## 10. 验收方案

### 10.1 离线测试（必须全绿）
```bash
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_re04_eval_dataset_loader.py \
  apps/api/tests/test_re04_resource_deduper.py \
  apps/api/tests/test_re04_resource_eval_offline.py \
  apps/api/tests/test_re04_main_entry.py \
  apps/api/tests/test_re04_work_package_binding.py -q
```

新增测试：
| 测试 | 验收 |
|---|---|
| `test_degradation_chain_present` | 返回 dict 含 `degradation_chain` |
| `test_heuristic_topic_has_baseline_query` | heuristic parse → baseline family 非空 |
| `test_seed_hit_count_threshold` | multi-word term 半数命中通过 |
| `test_baseline_degraded_marker_present` | 0 baseline + 有 parallel → `_baseline_degraded_marker` 非空 |
| `test_degraded_reason_in_round_delta` | round_delta 含降级原因 |

### 10.2 Online Smoke 5 重跑
```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/run_re04_smoke.py \
  --jsonl apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl \
  --ids apps/api/tests/fixtures/re04_smoke_20_ids.txt \
  --max 5 --out-dir tmp_re04_eval/smoke5_fixed
```

| Case | 修复前 | 修复后最低 |
|---|---|---|
| 015 | weak（3 baseline） | 维持或提升 |
| 016 | fail（0 baseline, 21 refs） | weak（≥1 降级 baseline，chain 含 self_cannot_find） |
| 018 | fail（预算断, 0 pool） | weak（预算取消后 pool 非空） |
| 024 | fail（预算断, 0 pool） | weak（同 018） |
| 027 | fail（0 baseline, ER 全 heuristic） | weak（≥1 降级 baseline，ER 非全 heuristic） |

### 10.3 degradation_chain 验收
每个 case raw dump 必须含非空 `degradation_chain`。016/027 必须出现 `self_cannot_find_baseline_degradation` 字样。report markdown 的 reason 列必须显示该标记。

### 10.4 聚合验收
```bash
.venv/Scripts/python.exe -m pytest apps/api/tests -q
```
全量通过，只增不减。

---

## 11. 参考资料引用（已核实存在）

### 11.1 AutoResearchClaw
- `search.py:104-231` — `search_papers()` 多源联合，query 不加语义标签，术语直搜
- `semantic_scholar.py:40-69` — 三态 circuit breaker（CLOSED/OPEN/HALF_OPEN），限流时跳过而非全量 heuristic
- `arxiv_client.py` — arXiv 搜索 query 全英文，无中文容错

### 11.2 academic-research-skills
- `literature_strategist_agent.md` §Search Strategy Design — 2-4 核心概念 + 同义词 + 布尔组合，不依赖单词全匹配
- `literature_strategist_agent.md` 第 516-530 行 §Chinese-English Literature Search Difference Handling — 中英文分开检索和评估

---

## 12. 提交规范

7 个修复 → 7 个独立 commit，每个 commit message 前缀 `re04-fix(n/7):`，便于回滚定位。

---

> 本 SOP 不引入 `*_score` 字段、不新增静态资源目录、不与 LLM-dead-path 产品化。
> 所有 fallback 路径在输出层显式标记 `degraded_reason` / `degraded_marker`。
> 降级 baseline 永远带 `self_cannot_find_baseline` 前缀，绝不冒充真 baseline。
