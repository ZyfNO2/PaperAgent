# PaperAgent Session 22 SOP：Renderer Component Registry 最小卡片库

> 日期：2026-06-20  
> 前置：Session 21 已有 Step Deck、mock stream、paperagent-card / pa-card 安全解析器。  
> 本轮目标：把 Session 21 中散落在 `step_deck.js` / `render_protocol.js` 里的卡片渲染逻辑收束成稳定的 Renderer Component Registry。

---

## 1. 本轮目标

```text
让所有 paperagent-card 都走统一注册表：
component -> schema -> renderer -> actions -> fallback
```

本轮解决的问题：

```text
1. 避免每新增一张卡就在 step_deck.js 里写 if/else；
2. 让白名单组件具备清晰 schema；
3. 让 action_id 统一注册；
4. 让非法组件、坏 props、未知 action 统一降级；
5. 给后续 S23 Prompt 协议提供稳定组件清单。
```

---

## 2. 不做什么

```text
不接真实 LLM；
不接真实 SSE；
不做插件市场；
不允许用户自定义 JS 组件；
不做 iframe 渲染；
不改 EvidenceRef / Verification / supports 规则；
不改 S17 baseline。
```

---

## 3. 建议文件

优先低风险落在前端：

```text
apps/web/component_registry.js
apps/web/render_protocol.js
apps/web/step_deck.js
apps/web/index.html
apps/web/e2e/test_one_topic_session22_component_registry.py
```

如果需要测试纯 JS registry，可新增：

```text
apps/web/e2e/test_one_topic_session22_render_registry.py
```

---

## 4. 最小组件清单

第一批只做 6 张核心卡：

```text
TopicUnderstandingCard
KeywordReviewCard
SearchQueryPlanCard
RetrievalCandidateCard
EvidenceRefCard
ReportQualityCard
```

其余白名单组件继续允许解析，但使用通用 JSON 摘要降级：

```text
EvidenceCard
VerificationCard
FeasibilityCard
PivotRouteCard
HumanReviewCard
FinalReportCard
TraceEventCard
```

---

## 5. Registry 结构

建议结构：

```js
const ComponentRegistry = {
  KeywordReviewCard: {
    schema: validateKeywordReviewCard,
    render: renderKeywordReviewCard,
    actions: ["approve_step", "revise_step", "regenerate_step"]
  }
}
```

每个组件必须具备：

```text
1. component name；
2. props schema；
3. render function；
4. allowed actions；
5. empty state；
6. invalid state；
7. Playwright selector contract。
```

---

## 6. 卡片字段建议

### TopicUnderstandingCard

```json
{
  "topic": "基于YOLO的钢材表面缺陷检测",
  "intent": "使用目标检测方法完成工业质检任务",
  "assumptions": ["存在公开数据集", "需要实时性"],
  "risks": ["数据集不足", "baseline不可复现"]
}
```

### KeywordReviewCard

```json
{
  "keywords": [
    {"kind": "method", "text": "YOLO"},
    {"kind": "task", "text": "目标检测"},
    {"kind": "object", "text": "钢材表面缺陷"}
  ],
  "editable": true
}
```

### SearchQueryPlanCard

```json
{
  "queries": [
    {"source": "paper", "query": "YOLO steel surface defect detection"},
    {"source": "dataset", "query": "steel surface defect dataset"},
    {"source": "repo", "query": "YOLO defect detection GitHub"}
  ],
  "requires_user_confirmation": false
}
```

### RetrievalCandidateCard

```json
{
  "kind": "paper",
  "title": "候选论文标题",
  "url": "https://example.com",
  "matched_keywords": ["YOLO", "defect detection"],
  "confidence": "candidate",
  "actions": ["save_candidate", "reject_candidate", "open_drawer"]
}
```

### EvidenceRefCard

```json
{
  "evidence_id": "ev_001",
  "source_type": "paper",
  "claim": "该方向存在公开数据集",
  "support_level": "candidate",
  "verified": false
}
```

### ReportQualityCard

```json
{
  "checks": [
    {"name": "题目是否过大", "status": "warn"},
    {"name": "数据来源是否明确", "status": "pass"}
  ]
}
```

---

## 7. Action 注册表

统一 action：

```text
approve_step
revise_step
regenerate_step
open_drawer
save_candidate
reject_candidate
promote_to_selected
mark_needs_review
```

限制：

```text
action 只能触发前端已注册 handler；
action 不允许携带 JS 字符串；
action 不允许直接写 Evidence Ledger；
action 只能产生 UI state 或请求后端固定 endpoint。
```

---

## 8. Playwright 验收

新增测试：

```text
S22-PW-1：6 类核心卡都能通过 registry 渲染；
S22-PW-2：未知 component 显示安全降级卡；
S22-PW-3：props 类型错误显示 invalid card；
S22-PW-4：未知 action 被拒绝；
S22-PW-5：KeywordReviewCard 仍能增删改；
S22-PW-6：SearchQueryPlanCard 显示 paper/dataset/repo 三类 query；
S22-PW-7：RetrievalCandidateCard 的 save/reject 不直接写 Evidence；
S22-PW-8：S21 Step Deck 主流程不回退。
```

---

## 9. 验收标准

```text
1. 新增 component registry；
2. render_protocol 使用 registry 校验 component/action；
3. step_deck 不再为每个组件散写主要渲染分支；
4. 6 类核心卡可稳定渲染；
5. 非法组件、坏 props、未知 action 可降级；
6. Playwright 覆盖 registry；
7. S21 keyword gate 仍可用；
8. S17 baseline 不回退。
```

---

## 10. 完工报告

完成后新增：

```text
Plan/reports/Session_22_ComponentRegistry_验收报告.md
```

报告必须写：

```text
1. registry 结构；
2. 支持的组件清单；
3. action 注册表；
4. 降级策略；
5. Playwright 结果；
6. 是否影响 S21；
7. 是否影响 S17 baseline；
8. 后续 S23 Prompt 协议需要遵守的组件合同。
```

