# PaperAgent Session 24 SOP：检索计划与候选资源卡

> 日期：2026-06-20  
> 前置：Session 22 完成组件注册表，Session 23 明确流式 Prompt 与工具调用边界。  
> 本轮目标：从用户确认后的关键词出发，生成论文、数据集、工程三个方向的检索计划与候选资源卡。候选资源只进入 Candidate，不直接成为 Evidence。

---

## 1. 本轮目标

```text
把 keyword_review 的确认结果转成可执行的 query_plan；
再把 query_plan 转成 candidate resource cards；
让用户能保存、淘汰、标记需要复核。
```

本轮只做候选，不做正式证据结论：

```text
Candidate != Evidence
Candidate URL != URLVerified
Candidate recommendation != supports
```

---

## 2. 不做什么

```text
不做大规模爬虫；
不做 PDF 全文解析；
不做向量库；
不做 DOCX；
不把候选资源直接写入开题报告；
不把未验证 URL 当作强证据；
不跳过 EvidenceRef / Verification。
```

---

## 3. 输入

来自 Session 21-23 的确认结果：

```json
{
  "topic": "基于YOLO的钢材表面缺陷检测",
  "approved_keywords": [
    {"kind": "method", "text": "YOLO"},
    {"kind": "task", "text": "目标检测"},
    {"kind": "object", "text": "钢材表面缺陷"},
    {"kind": "domain", "text": "工业质检"}
  ]
}
```

如果关键词未 approved：

```text
返回 blocked；
提示回到 keyword_review；
不得生成真实检索计划。
```

---

## 4. Query Plan

生成三类 query：

```text
paper queries；
dataset queries；
repo queries。
```

每类 query 至少包含：

```text
1. 中文 query；
2. 英文 query；
3. 来源关键词；
4. 预期资源类型；
5. 检索优先级；
6. 风险说明。
```

示例：

```json
{
  "source": "paper",
  "query": "YOLO steel surface defect detection",
  "keywords": ["YOLO", "steel surface defect", "detection"],
  "priority": "high",
  "reason": "验证是否已有类似方法和 baseline"
}
```

---

## 5. Candidate Resource

候选资源统一结构：

```json
{
  "candidate_id": "cand_001",
  "kind": "paper",
  "title": "候选资源标题",
  "url": "https://example.com",
  "source": "mock_or_real_source",
  "matched_keywords": ["YOLO", "defect detection"],
  "summary": "为什么可能有用",
  "risk_flags": ["url_unverified"],
  "status": "candidate",
  "user_mark": "unreviewed"
}
```

`kind` 允许：

```text
paper
dataset
repo
thesis_template
benchmark
```

`user_mark` 允许：

```text
unreviewed
saved
rejected
needs_review
selected
```

---

## 6. UI 卡片

使用 Session 22 的 Registry：

```text
SearchQueryPlanCard
RetrievalCandidateCard
EvidenceRefCard
TraceEventCard
```

候选卡动作：

```text
save_candidate
reject_candidate
mark_needs_review
promote_to_selected
open_drawer
```

动作约束：

```text
save_candidate 只进入候选收藏；
promote_to_selected 只进入“用户选中资料”，不等于 Evidence；
open_drawer 展示 URL / 摘要 / 匹配关键词 / Trace；
任何 action 都不能直接写 supports。
```

---

## 7. 数据来源策略

MVP 可按三档实现：

```text
A 档：纯 mock fixture；
B 档：复用现有检索服务的轻量结果；
C 档：真实外部检索，但必须允许失败降级。
```

推荐本轮先用 A+B：

```text
优先保证 UI / schema / Trace / Playwright；
真实联网检索可作为增强，不作为通过条件。
```

---

## 8. Trace 要求

必须记录：

```text
query_plan_created；
candidate_generated；
candidate_saved；
candidate_rejected；
candidate_marked_needs_review；
candidate_promoted_to_selected。
```

如果当前没有后端持久化：

```text
前端 eventBuffer 可先记录；
但验收报告必须明确“刷新丢失”；
后续 S25 前需要接入持久化。
```

---

## 9. Playwright 测试

新增：

```text
apps/web/e2e/test_one_topic_session24_candidate_cards.py
```

覆盖：

```text
S24-PW-1：未确认关键词时 query_plan blocked；
S24-PW-2：确认关键词后显示 paper/dataset/repo query；
S24-PW-3：生成候选资源卡；
S24-PW-4：候选卡显示 source URL 和 matched_keywords；
S24-PW-5：save_candidate 改变 user_mark；
S24-PW-6：reject_candidate 改变 user_mark；
S24-PW-7：promote_to_selected 不写 Evidence；
S24-PW-8：Trace drawer 可见候选操作；
S24-PW-9：S21 keyword gate 不回退；
S24-PW-10：非法 candidate card 降级。
```

---

## 10. 后端测试

如果本轮新增后端 candidate schema：

```text
apps/api/tests/test_session24_candidate_resources.py
```

覆盖：

```text
1. keyword 未 approved -> blocked；
2. approved_keywords -> query_plan；
3. query_plan -> candidates；
4. candidate 不等于 evidence；
5. candidate status 枚举校验；
6. URL 未验证时 risk_flags 包含 url_unverified；
7. 用户标记写 Trace；
8. S17 baseline 不回退。
```

---

## 11. 验收标准

```text
1. approved keywords 能生成 query_plan；
2. query_plan 至少包含 paper/dataset/repo 三类；
3. 候选资源卡可渲染；
4. 候选资源可保存、淘汰、标记复核；
5. 候选与 Evidence 明确隔离；
6. 操作进入 Trace；
7. Playwright 覆盖主路径；
8. 如有后端 schema，后端测试通过；
9. S17 baseline 不回退；
10. 验收报告明确真实检索是否已接入。
```

---

## 12. 完工报告

完成后新增：

```text
Plan/reports/Session_24_QueryPlan_CandidateCards_验收报告.md
```

报告必须写：

```text
1. query_plan 结构；
2. candidate schema；
3. 三类资源卡示例；
4. 用户标记动作；
5. Trace 记录；
6. 候选与 Evidence 的边界；
7. 测试结果；
8. 是否可以进入 Session 25 双栏工作台。
```

