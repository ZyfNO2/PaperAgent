# Task T6 Report — evidence_refs 用 clean_status / literature_role 门控

## Scope

修改 `apps/api/app/services/evidence_refs.py::build_feasibility_refs()`, 让关键证据引用:
1. 不再包含 `clean_status in (reject, quarantine)` 的自动 paper
2. 不再包含 `literature_role in (survey, irrelevant)` 的 paper
3. reason 不再写 `arXiv 命中, 相关性 0.10`, 改写关键词命中解释
4. 全部 paper 被门控挡掉时, 走"证据不足" fallback, 显示"待人工确认"

## Files Changed

- `apps/api/app/services/evidence_refs.py` — 加 `_filter_valid_evidence` / `_build_keyword_reason`, 改 `build_feasibility_refs`
- `apps/api/tests/test_session65_t6_evidence_filter.py` — 新增 10 个测试

## Implementation

### 1. `_filter_valid_evidence(papers)`

门控规则:
- `clean_status in ("reject", "quarantine")` → 排除
- `literature_role in ("survey", "irrelevant")` → 排除
- 输入兼容 dict / Pydantic 对象 / SimpleNamespace

### 2. `_build_keyword_reason(item, topic_keywords)`

拼接格式:
```text
命中关键词: U-Net / 裂缝；缺失: 钢材 / 数据集；状态: 待人工确认
```

关键词来源优先 `topic_keywords` 参数, 落回 `item.matched_keywords / item.topic_atoms`; 都没有则输出"无题目录入"。

### 3. `build_feasibility_refs()` 改造

- 新增 `topic_keywords: list[str] | None` 参数
- 入口先 `_filter_valid_evidence(papers)`
- `by_type["paper"]` 分类时, 自动 paper 还要再过 `valid_paper_eid_strs` 白名单 (extras 信任用户, 不过滤)
- 全部自动 paper 被门控挡掉 且 extras 没 paper → 走 fallback:
  - `evidence_refs = []`
  - `confidence = 0.0`
  - `missing_ref_reasons = ["证据不足：未找到与题目匹配的论文候选", "过滤掉 N 个无关 / survey / 拒收候选；状态: 待人工确认"]`
  - `verdict`: "可做" → "收缩后可做"

## Hard Rules Compliance

| 规则 | 实现 |
|---|---|
| Reject/quarantine papers MUST NOT be in supports | ✓ `_filter_valid_evidence` + `by_type` 白名单 |
| Irrelevant/survey papers MUST NOT be in supports | ✓ 同上 |
| reason 应该用 keyword match, not numeric score | ✓ `_build_keyword_reason` |
| If no valid evidence, show "待人工确认" | ✓ fallback `missing_ref_reasons` |

## Tests

`apps/api/tests/test_session65_t6_evidence_filter.py` 10 个测试:

| 测试 | 验证 |
|---|---|
| test_rejected_clean_status_not_in_supports | `clean_status=reject` 不进 supports |
| test_quarantine_clean_status_not_in_supports | `clean_status=quarantine` 不进 supports |
| test_survey_role_not_in_supports | `literature_role=survey` 不进 supports |
| test_irrelevant_role_not_in_supports | `literature_role=irrelevant` 不进 supports |
| test_survey_paper_not_in_background_either | survey-only 触发"证据不足"fallback |
| test_reason_uses_keyword_match_not_score | reason 不含"相关性", 含"命中关键词" |
| test_reason_lists_missing_keywords | reason 列出缺失关键词 |
| test_all_papers_filtered_triggers_evidence_gap_fallback | 全过滤触发"证据不足" |
| test_extras_paper_can_rescue_from_evidence_gap | extras 能救场 (信任用户入池) |
| test_pydantic_object_paper_does_not_crash | Pydantic 对象不崩 |

### Test Results

- 新增 10 个: **全部通过**
- 现有 session 7 (12 个) + session 64 (33 个) 全部通过, **无回归**
- 全套 985 pass / 11 fail — 失败项均为 pre-existing (heuristic 数据集匹配, changelog, llm_path 等), 与本次改动无关

## What's NOT done (deliberate scope-cut)

- `build_pivot_refs / build_wp_refs / build_review_refs / build_proposal_refs` 暂未加门控 — 本轮 T6 只针对 SOP §6.2 点名的 `build_feasibility_refs`。其他几个 `build_*_refs` 后续 T 任务按需扩展, 避免本轮 diff 爆炸
- `topic_keywords` 还没从上游 (`one_topic.py`) 传进来 — 留作下游 T 任务接线; 当前 reason 落回 `item.matched_keywords / topic_atoms`, 仍能输出可读解释
- 没动 LLM path — `build_feasibility_refs` 仍是 heuristic 路径, 不影响 LLM 一致性

## Verification

```bash
# 新增测试
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session65_t6_evidence_filter.py -v
# 10 passed

# 回归测试
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session7_evidence_refs.py apps/api/tests/test_session64_literature_roles.py apps/api/tests/test_session64_candidate_cleaner.py apps/api/tests/test_session64_t1_candidate_cleaner.py -v
# 12 + 6 + 14 + 13 = 45 passed
```

## Commit

`Phase 65 T6: fix evidence_refs - use clean_status, remove score`
