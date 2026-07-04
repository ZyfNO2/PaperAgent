# PaperAgent Re04-fix 代码修复方案

> 起草日：2026-07-02
> 范围：仅修复 Re04 Online Smoke 5 暴露的 5 个代码级缺陷。
> 参考资料：
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\search.py`
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\semantic_scholar.py`
> - `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-paper\agents\literature_strategist_agent.md`
> - `Plan\PaperAgent_Re04_审计细节_保留与剔除.md`
> - `Plan\PaperAgent_Re04_完工报告.md`

---

## 目录

1. [诊断：5 个代码级缺陷](#1-诊断5-个代码级缺陷)
2. [修复 1：query_matrix baseline_family 生成缺陷](#2-修复-1query_matrix-baseline_family-生成缺陷)
3. [修复 2：seed_relevance 全词匹配过严](#3-修复-2seed_relevance-全词匹配过严)
4. [修复 3：证据审查 LLM ER 中文 JSON 解析全量失败](#4-修复-3证据审查-llm-er-中文-json-解析全量失败)
5. [修复 4：result_expander 中文乱码 query](#5-修复-4result_expander-中文乱码-query)
6. [修复 5：degradation_chain 全局可追溯链](#6-修复-5degradation_chain-全局可追溯链)
7. [执行边界与禁止行为](#7-执行边界与禁止行为)
8. [验收方案](#8-验收方案)
9. [参考资料引用](#9-参考资料引用)

---

## 1. 诊断：5 个代码级缺陷

Online Smoke 5 的 1 weak + 4 fail 由两条独立失败路径产生：

```
Path A (纯中文题目 — Case 027)
  LLM parse 失败 → _heuristic_parse → method_terms=[]
  → query_matrix "if method:" 跳过 → baseline_family=[]
  → adapter 全员英文 query=空 → crossref 靠 fb_atom（中文）返回 8 篇
  → expand_from_round1 从中文 tokens 拼 garbled query → S2 返回 JATS 噪声
  → seed_relevance 因 method_terms=[] 全拒 seed → citation_expand=0 refs
  → LLM ER 中英混合 pool → JSON parse 连败 2 次 → 16/16 heuristic default
  → synthesis 无 baseline 可靠 → low_bar 强制 needs_revision

Path B (混合题目 — Case 016)
  LLM parse 成功 → method_terms=["visual SLAM", ...]
  → query_matrix baseline=["visual SLAM classic", ...] → "classic" 无效
  → crossref 只返回 VO 论文（crossref "visual SLAM"→"visual odometry"）
  → seed_relevance → "visual SLAM" 要求 visual+slam 都在 → VO 论文命中 visual 缺 slam → rule 1 fail
  → seed 全拒 → citation_expand=0 refs
  → LLM ER 把 21/21 全部判 candidate（理由是"有匹配但不全"）
  → 无 core → 无 baseline → low_bar 强制 needs_revision
```

| # | 文件名 | 行号 | 缺陷 | 影响 case | 修复类型 |
|---|---|---|---|---|---|
| 1 | `query_matrix.py` | 136-139 | `if method:` 在 `method_terms=[]` 时 baseline query 零产出 | 027 | 结构性 bug |
| 2 | `seed_relevance.py` | 56 | `all(w in haystack_tokens for w in words)` 要求 multi-word term 所有词都在 | 016 | 设计阈值 |
| 3 | `evidence_review.py` | 207-244 | 中英混合候选池 → LLM JSON parse 两次全败 → 全量 heuristic | 027 | 降级路径缺失 |
| 4 | `result_expander.py` | 40-104 | 中文 token → garbled query → 适配器返回噪声 | 027 | 滤波缺失 |
| 5 | `re04_entry.py` | 344-356 | 无 per-case 根因链聚合，审计需要人工串联多轮 | 全部 | 可观测性 |

每个修复必须满足：
- **降级要自标记**：fallback 路径的输出必须显式声明"这是降级"
- **不动外层接口**：不改变 `run_research_agent_re04()` 的返回 schema，只增字段
- **可回滚**：每个修复一个独立 commit

---

## 2. 修复 1：query_matrix baseline_family 生成缺陷

### 2.1 当前代码

`apps/api/app/services/agents/query_matrix.py:136-139`：

```python
baseline_family: list[str] = []
if method:
    for m in method[:2]:
        baseline_family.append(_join(m, "classic"))
```

问题：
- `if method:` 在 `method_terms=[]` 时直接跳过（Case 027 → 无任何 baseline query）
- `"classic"` 后缀在 arxiv / crossref / openalex 搜索中无实际过滤效果

### 2.2 修复代码

```python
# ── baseline_family (Re04-fix: 4 层退路) ──
baseline_family: list[str] = []
_baseline_fallback_reason: str | None = None  # 降级标记

# 第一优先：method + task 组合（最精确）
if method and task:
    for m in method[:2]:
        for t in task[:2]:
            q = _join(m, t)
            if q:
                baseline_family.append(q)

# 第二退路：仅 method_terms
if not baseline_family and method:
    baseline_family = [m for m in method[:2] if m]
    if not method or not task:
        _baseline_fallback_reason = "no_task_terms_use_method_only"

# 第三退路：仅 task_terms（针对 method=[] 但 task 非空的中文题目）
if not baseline_family and task:
    baseline_family = [t for t in task[:2] if t]
    _baseline_fallback_reason = "no_method_terms_use_task_only"

# 最终退路：fb_atom（用户原文，明确标记降级）
if not baseline_family and fb_atom:
    baseline_family.append(fb_atom)
    _baseline_fallback_reason = "no_lexical_terms_use_raw_topic_fallback"
```

### 2.3 降级标记

在 `query_matrix` 返回字典中新增 `"baseline_fallback_reason"` 字段：

```python
return {
    # ... 原有字段不变 ...
    "baseline_fallback_reason": _baseline_fallback_reason,
    "baseline_queries": baseline_family[:4],
}
```

当 `_baseline_fallback_reason` 非空时，`re04_entry.py` 的 `round_delta["R0_query_matrix"]` 自动聚合进 `degradation_chain`。

### 2.4 可验证行为

| case | method | task | fb_atom | 原来 | 修复后 | fallback_reason |
|------|--------|------|---------|------|--------|-----------------|
| 027 | [] | [] | "基于YOLOv5..." | **[]** | ["基于YOLOv5..."] | `no_lexical_terms_use_raw_topic_fallback` |
| 016 | ["visual SLAM",...] | ["visual odometry",...] | any | ["visual SLAM classic"] | ["visual SLAM visual odometry"] | `null`（无降级） |
| 015 | ["3D reconstruction",...] | ["patient positioning",...] | any | ["3D reconstruction classic"] | ["3D reconstruction patient positioning"] | `null`（无降级） |

### 2.5 参考资料

AutoResearchClaw `search.py:113-130` 中的 `search_papers()` 对 query 不加 baseline/survey/etc 标签，query = 实际学术术语直接匹配。其 `search_papers_multi_query()` 对多个 query 做 union，不区分"这个 query 是 baseline 用的"——本文修复借鉴其"术语直搜不做后缀"原则，仅精简 query 本身。

---

## 3. 修复 2：seed_relevance 全词匹配过严

### 3.1 当前代码

`apps/api/app/services/agents/seed_relevance.py:47-60`：

```python
def _hit_count(terms, haystack_tokens):
    hits = []
    for t in terms:
        words = re.findall(r"[a-z0-9一-鿿]{2,}", tl)
        if all(w in haystack_tokens for w in words):  # 必须每个词都命中
            hits.append(t)
    return len(hits), hits
```

问题：`all(w in haystack_tokens)` 要求 multi-word term 的所有词都必须出现在 title/abstract 的 tokens 中。"visual SLAM" → 候选标题 "Visual Odometry Based on CNN" → tokens 含 `visual` 但不含 `slam` → method_hits=0 → rule 1 fail。

### 3.2 修复代码

```python
def _hit_count(terms: Iterable[str], haystack_tokens: set[str]) -> tuple[int, list[str]]:
    """Re04-fix：多词 term 改用阈值匹配（≥ 半数词命中即为匹配）。

    当 seed_relevance._hit_count 使用阈值而非全词匹配时，
    evaluate_seed 返回的 matched_axis 会附加 "threshold" 后缀作为降级标记。
    """
    hits: list[str] = []
    for t in terms:
        if not t:
            continue
        tl = t.lower().strip()
        words = re.findall(r"[a-z0-9一-鿿]{2,}", tl)
        if not words:
            continue
        # Re04-fix: ≥ ceil(len(words)/2) 个词命中即算匹配
        threshold = (len(words) + 1) // 2
        matched_words = [w for w in words if w in haystack_tokens]
        if len(matched_words) >= threshold:
            hits.append(t)
    return len(hits), hits
```

### 3.3 降级标记

在 `evaluate_seed()` 返回中新增 `matched_mode: "threshold"`：

```python
return {
    "candidate_id": cid,
    "seed_eligible": matched_axis != "none",
    "matched_axis": f"{matched_axis}_threshold" if matched_axis != "none" and matched_words else matched_axis,
    #   ^^^ 凡触发了阈值匹配的，axis 末尾加 _threshold
    "matched_terms": matched_terms[:8],
    "rejected_reason": rejected_reason,
    "_debug": {
        "method_hits": method_hits,
        "task_hits": task_hits,
        "object_hits": object_hits,
        "atom_hits": len(atom_matched),
        "matched_mode": "threshold",  # 新增降级标记
    },
}
```

### 3.4 可验证行为

| seed | term | words | title tokens | 原来 | 修复后 |
|------|------|-------|-------------|------|--------|
| Visual Odometry Based on CNN | "visual SLAM" | `{visual, slam}` | `{visual, odometry, based, cnn, slam}` | hit | hit（同） |
| Visual Odometry Based on CNN | "visual SLAM" | `{visual, slam}` | `{visual, odometry, based, cnn}` | miss (缺 slam) | **hit**（threshold=1） |
| Comparative Analysis of Monocular VO | "semantic mapping" | `{semantic, mapping}` | `{visual, odometry, methods, indoor}` | miss (缺 2/2) | miss（threshold=1 但 0/2） |

### 3.5 参考资料

academic-research-skills `literature_strategist_agent.md` 中 "Search String Construction" 使用布尔组合 `("concept A" OR "synonym A1") AND ("concept B" ...)`，其筛选不是"标题里所有词都匹配"的刚性需求。同时 AutoResearchClaw 的 `_deduplicate()` 在 DOI→arXiv→title 三个维度做 OR 联合决定，而非 AND。本文修复的原则一致性：multi-word 条件变 OR-like，提高 recall。

---

## 4. 修复 3：证据审查 LLM ER 中文 JSON 解析全量失败

### 4.1 当前代码

`apps/api/app/services/agents/evidence_review.py:207-244`：

```python
for attempt, (max_t, timeout) in enumerate(
    [(base_max, base_timeout), (base_max * 2, base_timeout + 60.0)]
):
    try:
        out = chat_json_strict(prompt, EVIDENCE_REVIEW_SYSTEM, ...)
        # ... 解析 ...
        success = True
        break
    except ...:
        last_error = ...

if not success:
    for c in chunk:
        blocked.add(c["candidate_id"])
        reviews.append(_heuristic_review_for(c))  # 全量 heuristic
```

问题：中英混合候选池 → MiniMax M3 返回的 JSON 两次都无法 parse → 16/16 全 heuristic default。

### 4.2 修复代码

**A. 中文检测**（新增函数）：

```python
def _has_majority_chinese(chunk: list[dict]) -> bool:
    """当候选 title 中 >50% 含中文字符 → 走中文 prompt + 小 chunk"""
    chinese_count = sum(
        1 for c in chunk
        if any('一' <= ch <= '鿿' for ch in c.get('title', ''))
    )
    return chinese_count > len(chunk) // 2
```

**B. chunk 选择 + prompt 选择**（改动 `_audit_one_chunk` 调用处）：

```python
# 在 audit_candidates 中，每个 chunk 被构建前检测
if candidates:
    # 全局检测：大部分 candidate 含中文 → 换 prompt + 换 chunk_size
    import os
    is_chinese = _has_majority_chinese(candidates)
    if is_chinese:
        chunk_size = max(5, int(os.environ.get("PAPERAGENT_ER_CHUNK_SIZE", "20")) // 2)
    else:
        chunk_size = int(os.environ.get("PAPERAGENT_ER_CHUNK_SIZE", "20"))
    # ... 用新 chunk_size 切分 ...
```

**C. 第三次兜底重试**（改动 `_audit_one_chunk` 的重试循环）：

```python
# 在现有 2 次重试后新增：
if not success and len(chunk) > 3:
    # 第三次兜底：逐个候选评（chunk_size=1，max_tokens=6000 per candidate）
    logger.warning("EvidenceReview chunk %d: falling back to per-candidate review", chunk_idx)
    per_candidate_reviews, per_candidate_blocked = [], set()
    for single_candidate in chunk:
        try:
            out = chat_json_strict(
                USER_TEMPLATE_EVIDENCE_REVIEW.format(
                    parsed_topic=json.dumps(parsed_topic, ensure_ascii=False),
                    candidates_block=json.dumps(
                        [{"candidate_id": single_candidate["candidate_id"],
                          "title": single_candidate.get("title", "")[:200]}],
                        ensure_ascii=False,
                    ),
                    raw_block="",
                ),
                RE04_EVIDENCE_REVIEW_SYSTEM if is_chinese else EVIDENCE_REVIEW_SYSTEM,
                max_tokens=6000,
                timeout=120.0,
            )
            row = out.get("reviews", [{}])[0]
            per_candidate_reviews.append(_normalize_review(row, single_candidate["candidate_id"]))
        except Exception:
            per_candidate_blocked.add(single_candidate["candidate_id"])
            per_candidate_reviews.append(_heuristic_review_for(single_candidate))

    # 替换全量 heuristic 为 per_candidate 结果
    reviews = per_candidate_reviews
    blocked = per_candidate_blocked
    success = True  # 至少试过逐个评，即使部分 heuristic
```

**D. 降级标记**（在 heuristic review 中区分来源）：

```python
def _heuristic_review_for(c, *, degraded_from: str = ""):
    tag = degraded_from or "llm_blocker: evidence_review_parse_failed"
    # "degraded_from" 在 per_candidate 兜底时 = "chinese_chunk_llm_per_candidate_fallback"
    # 在无兜底时保持原 "llm_blocker: evidence_review_parse_failed"
```

### 4.3 降级标记

| 场景 | reason 内标签 |
|------|--------------|
| per-candidate 兜底成功 | `[degraded: chunk_fallback_per_candidate]` |
| per-candidate 兜底也失败 | `[degraded: chunk_fallback_per_candidate_failed]` |
| 无中文检测（原逻辑） | `[llm_blocker: evidence_review_parse_failed]` |

### 4.4 可验证行为

- Case 027 重跑后：16 篇不再全量 `llm_blocker`，至少 8/16 有 per-candidate LLM 评审
- 回归测试：Case 015 仍然用 EVIDENCE_REVIEW_SYSTEM（英文 prompt），不受影响

### 4.5 参考资料

academic-research-skills `literature_strategist_agent.md` §"Chinese-English Literature Search Difference Handling" 第 3-5 行明确要求分语言检索和分语言评估。AutoResearchClaw `semantic_scholar.py` 的 `search_semantic_scholar()` 对任何 query 语言不做区分，但因为它只接受英文 query（arXiv 的顶层 API），中文 query 发送方已经做了过滤。本文修复的"中文候选 => 中文 prompt + 更小 chunk"与此一致：不是改 LLM，而是让 LLM 接触更少、更清晰的上下文。

---

## 5. 修复 4：result_expander 中文乱码 query

### 5.1 当前代码

`apps/api/app/services/agents/result_expander.py:40-104`：

```python
_TOKEN_RE = re.compile(r"[a-z0-9一-鿿]{2,}")

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]
```

当 text 为中文时，`_tokens()` 返回中文 tokens，后续拼接成 query（如 `"etection v7|etection jats|etection 我们的"`）发给 S2 → S2 返回无关噪声。

### 5.2 修复代码

**A. 滤波函数**（新增）：

```python
def _is_chinese_dominated(text: str, threshold: float = 0.5) -> bool:
    """中文占比 ≥ threshold → 对英文学术搜索 API 无效"""
    if not text:
        return False
    chinese = sum(1 for ch in text if '一' <= ch <= '鿿')
    return chinese / max(len(text), 1) > threshold


def _filter_english_tokens(tokens: list[str]) -> list[str]:
    """保留纯英文或英文为主的 tokens"""
    return [t for t in tokens if not _is_chinese_dominated(t)]
```

**B. expand_from_round1 改动**（`result_expander.py:56-62`）：

```python
def expand_from_round1(r1_raw, *, parsed_topic=None, top_method_k=4, top_object_k=4):
    # ... token 提取不变 ...
    for adapter in ("arxiv", "openalex", "crossref"):
        for item in r1_raw.get(adapter) or []:
            text = f"{title} {abstract}"
            for tok in _tokens(text):
                # Re04-fix: 跳过中文 dominated tokens
                if not _is_chinese_dominated(tok):
                    method_counter[tok] += 1
            for tok in _tokens(item.get("abstract") or ""):
                if not _is_chinese_dominated(tok):
                    object_counter[tok] += 1
    # ...
    # 构建 queries
    out = []
    for m in methods:
        for o in objects:
            q = _word_cap(f"{m} {o}", 6)
            if q and not _is_chinese_dominated(q):
                out.append({"query": q, ...})
    # ...
```

**C. 全中文时跳过低级**（`expand_from_round1` 返回空时）：

当 round 2 全部 filtered out → `r2_added = []` → ledger 记录 `degraded: all_queries_garbled_skipped`。

### 5.3 降级标记

```python
# 在 expand_from_round1 返回前
if not out and any(_is_chinese_dominated(q) for q in out_before_filter):
    # 记录降级标记到 parsed_topic 透传
    return out, {"degraded_reason": "all_queries_chinese_garbled_skipped"}
else:
    return out, {}
```

`re04_entry.py` 中读取这个标记写入 `round_delta["R2_dynamic_expansion"]["degraded_reason"]`。

### 5.4 可验证行为

- Case 027 重跑后：Round 2 query 不再含 `"etection v7"` 等乱码 → round_delta 标记 `degraded`
- Ledger 不出现 `"etection v7|etection jats|..."` 的 entry

### 5.5 参考资料

AutoResearchClaw 的 `arxiv_client.py` 使用 `arxiv.Search(query=query)` — 其 query 是全英文的；`openalex_client.py` 同理。整个 AutoResearchClaw 的 literature 模块不接受中文 query（没有中英混合容错），因为 arXiv 搜索 API 不支持中文。本文修复选择"检测到 garbled 就 skip，不尝试发中文给英文 API"与之方向一致。

---

## 6. 修复 5：degradation_chain 全局可追溯链

### 6.1 问题

当前 round_delta 每轮独立，审计需要人工跨 round 串联。例如一个 0 baseline case，人需要单独看 parsed_topic → query_matrix → family counts → seed gate → ER status → synthesis verdict 才能定位根因。

### 6.2 修复代码

在 `run_research_agent_re04()` 返回前新增聚合逻辑（`re04_entry.py`）：

```python
def _build_degradation_chain(
    parsed, qm, pool, reviews, synthesis, ce_stats, r2_delta, round_delta
) -> list[str]:
    chain = []

    # 1) parse 降级
    if parsed.get("_heuristic"):
        chain.append("parse:heuristic_fallback")

    # 2) query_matrix 降级
    qm_bfr = qm.get("baseline_fallback_reason")
    if qm_bfr:
        chain.append(f"query_matrix:baseline_{qm_bfr}")
    zero_baseline_query = len((qm.get("query_families") or {}).get("baseline", [])) == 0
    if zero_baseline_query:
        chain.append("query_matrix:zero_baseline_queries")
    zero_dataset_query = len((qm.get("query_families") or {}).get("dataset", [])) == 0
    if zero_dataset_query:
        chain.append("query_matrix:zero_dataset_queries")

    # 3) Round 1 adapter 结果
    r1 = round_delta.get("R1_family_dispatch", {})
    per_adapter = r1.get("per_adapter", {})
    if not per_adapter:
        chain.append("r1:all_adapters_empty")

    # 4) Round 2 降级
    r2_degraded = r2_delta.get("degraded_reason")
    if r2_degraded:
        chain.append(f"r2:{r2_degraded}")

    # 5) seed_relevance gate
    if ce_stats:
        total = ce_stats.get("seeds_total", 0)
        eligible = ce_stats.get("seeds_eligible", 0)
        if total > 0 and eligible == 0:
            # 检查是否有 seed 用了阈值匹配
            chain.append("citation_expand:all_seeds_rejected")

    # 6) ER 降级
    if reviews:
        blocked = sum(1 for r in reviews if "llm_blocker" in (r.reason or ""))
        degraded = sum(1 for r in reviews if "degraded:" in (r.reason or ""))
        if blocked == len(reviews):
            chain.append("evidence_review:all_heuristic_blocked")
        elif blocked > 0:
            chain.append(f"evidence_review:{blocked}_of_{len(reviews)}_blocked")
        if degraded > 0:
            chain.append(f"evidence_review:{degraded}_degraded")

    # 7) 无 baseline
    pool_papers = pool.by_evidence_type("paper") if hasattr(pool, "by_evidence_type") else []
    pool_baselines = [p for p in pool_papers if p.get("role_hint") == "baseline"]
    if not pool_baselines:
        chain.append("pool:zero_baseline_candidates")

    return chain
```

### 6.3 输出位置

```python
# 在 run_research_agent_re04 返回字典中新增
return {
    # ... 原有所有字段不变 ...
    "degradation_chain": degradation_chain,
}
```

### 6.4 可验证行为

- Case 027 预计 chain：`["parse:heuristic_fallback", "query_matrix:baseline_no_lexical_terms_use_raw_topic_fallback", "query_matrix:zero_dataset_queries", "r1:all_queries_chinese_garbled_skipped", "evidence_review:all_heuristic_blocked", "pool:zero_baseline_candidates"]`
- Case 016 预计 chain：`["citation_expand:all_seeds_rejected", "pool:zero_baseline_candidates"]`
- 低栏评审者直接读取 `degradation_chain`，写入 weak_points

### 6.5 参考资料

academic-research-skills 的 "IRON RULE: every claim needs citation" 原则要求来源可追溯，类似地本修复的 degradation_chain 让每个失败原因可追溯。AutoResearchClaw 的 circuit breaker (`semantic_scholar.py`) 总是在有限源失败后尝试下一个源并记录转移，本文的 chain 机制为此提供了输出侧的对等物。

---

## 7. 执行边界与禁止行为

### 7.1 范围内

- ✅ 上面 5 个修复的具体代码改动
- ✅ 降级标记落地（所有 fallback 路径在输出中有显式标记）
- ✅ 修改测试用例验证降级标记存在
- ✅ 重跑 Case 027 确认 chain 完整、baseline 非空
- ✅ 重跑 Case 016 确认 seed_gate 至少通过部分 seed
- ✅ `uv run pytest` 全绿后 commit（5 个 fix 可 1 个 commit 或 5 个独立 commit）

### 7.2 范围外（禁止）

- ❌ 不修改 `query_atoms_en` 生成逻辑（不在 query_matrix 里加 LLM 调用）
- ❌ 不修改 LLM ER 的 `EVIDENCE_REVIEW_SYSTEM` 英文 prompt 内容（只加中文检测和切换）
- ❌ 不新增 `*_score` 字段（S66v 规则）
- ❌ 不新增静态 baseline/dataset 目录（S66v 规则）
- ❌ 不修改 `crossref_search.py` 等适配器代码
- ❌ 不修改 `seed_relevance.py` 的 `evaluate_seed()` 外层排序逻辑
- ❌ 不在此阶段跑 balanced 40（那是验收后才做的）

### 7.3 禁止的偷懒行为

| 禁止 | 原因 |
|------|------|
| seed_relevance 修复改为 `always eligible` | 会通过离题种子引入引用噪声 |
| ER 修复改为直接 `pass` 所有中文候选 | 违反 S66v "不泄题" 规则 |
| 降级标记藏在 debug 字段不写文档 | 违反"自标记"要求 |
| 不在测试中覆盖降级标记断言 | 降级标记是验收的关键证据 |
| 用 `if "YOLOv5" in title: keep` 替代 ER | 违反 S66v "不用 hardcoded 白名单" |
| 一次改完不逐个 commit | 违反"可回滚"要求 |

---

## 8. 验收方案

### 8.1 离线测试（必须全绿）

```bash
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_re04_eval_dataset_loader.py \
  apps/api/tests/test_re04_resource_deduper.py \
  apps/api/tests/test_re04_resource_eval_offline.py \
  apps/api/tests/test_re04_main_entry.py \
  apps/api/tests/test_re04_work_package_binding.py -q
```

**新增测试**：

| 测试模块 | 新增测试 | 验收内容 |
|---------|---------|---------|
| `test_re04_main_entry.py` | `test_degradation_chain_present` | 返回 dict 含 `degradation_chain` |
| `test_re04_main_entry.py` | `test_heuristic_topic_has_baseline_query` | heuristic parse → baseline family 非空 |
| 新文件或 seed_relevance 测试 | `test_seed_hit_count_threshold` | multi-word term 部分匹配通过 |
| `test_re04_main_entry.py` | `test_degraded_reason_in_round_delta` | round_delta 含降级原因 |

### 8.2 Online Smoke 5 重跑

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/run_re04_smoke.py \
  --jsonl apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl \
  --ids apps/api/tests/fixtures/re04_smoke_20_ids.txt \
  --max 5 \
  --out-dir tmp_re04_eval/smoke5_fixed
```

**Case 级别验收**：

| Case | 修复前 | 修复后最低 |
|------|--------|-----------|
| 015 | weak（3 baseline） | 维持或提升 |
| 016 | fail（0 baseline, 21 refs） | weak（≥1 baseline, degradation_chain 含 seed 原因） |
| 018 | fail（LLM 预算耗尽, 0 pool） | 修复在 budget 取消后 → weak |
| 024 | fail（LLM 预算耗尽, 0 pool） | 修复在 budget 取消后 → weak |
| 027 | fail（0 baseline, ER 全 heuristic） | weak（≥1 baseline, ER 非全 heuristic） |

### 8.3 degradation_chain 验收

每个 case 的 raw dump 必须包含非空 `degradation_chain`。Chain 必须准确反映实际失败路径（例如 Case 027 必须有 `parse:heuristic_fallback` 和 `query_matrix:baseline_no_lexical_terms_use_raw_topic_fallback`）。

### 8.4 聚合验收

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest apps/api/tests -q  # 全部
```

全量 pytest 通过，不减少现有测试（只增不减）。

---

## 9. 参考资料引用

### 9.1 AutoResearchClaw

- `search.py:104-231` — `search_papers()` 多源联合检索，query 不加语义标签（baseline/survey），直接用术语搜
- `search.py:233-265` — `search_papers_multi_query()` 多 query union 后去重，不区分"这个是 baseline query"
- `search.py:279-358` — `_deduplicate()` DOI→arXiv→title 三级回退，非刚性全匹配
- `semantic_scholar.py:43-61` — circuit breaker 三态（CLOSED/OPEN/HALF_OPEN），限流时自动跳过而非全量 heuristic
- `arxiv_client.py:135-204` — arXiv 搜索，query 全英文，无中文容错

### 9.2 academic-research-skills

- `literature_strategist_agent.md` §"Search Strategy Design" — 2-4 个核心概念 + 同义词 + 布尔组合，不依赖单个词全匹配
- `literature_strategist_agent.md` §"Chinese-English Literature Search Difference Handling" — 中英文分开检索和评估
- `literature_strategist_agent.md` §"Screening Decision Tree" — 分多层审查而非单一分数闸门

---

> 本方案不引入任何 `*_score` 字段、不新增静态资源目录、不与 LLM-dead-path 产品化。  
> 所有修复的 fallback 路径都在输出层显式标记 `degraded_reason`。
