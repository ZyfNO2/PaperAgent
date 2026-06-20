# Session 22 验收报告：Renderer Component Registry 最小卡片库

> 日期：2026-06-21  
> SOP：`Plan/PaperAgent_Session22_RendererComponentRegistry最小卡片库SOP.md`  
> 实现：`apps/web/component_registry.js`  
> 测试：`apps/web/e2e/test_one_topic_session22_component_registry.py`

---

## 1. Registry 结构

`ComponentRegistry` 采用统一注册表模式，所有 `paperagent-card` 走同一条渲染管线：

```text
component (name) → schema (validator) → renderer (render function) → actions (whitelist) → fallback (降级)
```

核心实现位于 `apps/web/component_registry.js`，以 IIFE 挂载到 `window.ComponentRegistry`。

**对外接口：**

| 方法 | 说明 |
|------|------|
| `register(name, def)` | 注册组件（内部使用） |
| `get(name)` | 获取组件定义，不存在返回 `null` |
| `has(name)` | 判断组件是否已注册 |
| `isActionAllowed(componentName, actionId)` | 校验 action 是否在组件白名单内 |
| `validateCard(card)` | 校验 card 结构 + props schema，返回 `{ ok, error?, fallback? }` |
| `renderCard(card)` | 完整渲染管线：校验 → 降级判断 → 渲染 |
| `renderInvalidCard(card, error)` | 安全降级卡（bad props） |
| `renderFallbackJSON(card)` | 通用 JSON 摘要卡（白名单非核心卡） |

**每个组件定义包含：**

- `schema` — props 校验函数
- `render` — HTML 渲染函数
- `actions` — 允许的 action_id 白名单
- `selector` — Playwright 选择器契约（如 `.pa-card--KeywordReviewCard`）

**兼容性处理：** `renderCard()` 同时支持 `card.component` 和 `card.type` 两种字段名（兼容 S21 `run_state` 的 `type` 字段）。

---

## 2. 支持的组件清单

### 6 张核心卡（带 schema 校验 + 专用渲染器）

| # | 组件名 | Schema 关键校验 | 允许 Actions |
|---|--------|-----------------|--------------|
| 1 | `TopicUnderstandingCard` | `topic` 为必填 string | `[]`（只读） |
| 2 | `KeywordReviewCard` | `keywords` 为数组，每项有 `text` | `approve_step`, `revise_step`, `regenerate_step` |
| 3 | `SearchQueryPlanCard` | `queries` 为数组，每项有 `query` | `approve_step`, `revise_step` |
| 4 | `RetrievalCandidateCard` | `kind` + `title` + `matched_keywords` 必填 | `save_candidate`, `reject_candidate`, `open_drawer` |
| 5 | `EvidenceRefCard` | `evidence_id` + `source_type` + `claim` 必填 | `mark_needs_review` |
| 6 | `ReportQualityCard` | `checks` 为数组，每项 `name` + `status ∈ {pass, warn, fail}` | `[]`（只读） |

### 7 张 fallback JSON 降级卡（白名单内、非核心）

这些组件可被解析，但使用通用 JSON 摘要渲染（`renderFallbackJSON`）：

- `EvidenceCard`
- `VerificationCard`
- `FeasibilityCard`
- `PivotRouteCard`
- `HumanReviewCard`
- `FinalReportCard`
- `TraceEventCard`

---

## 3. Action 注册表

统一 action 列表（SOP §7）：

| Action ID | 绑定组件 | 说明 |
|-----------|----------|------|
| `approve_step` | KeywordReviewCard, SearchQueryPlanCard | 确认当前步骤并推进 |
| `revise_step` | KeywordReviewCard, SearchQueryPlanCard | 修改后继续 |
| `regenerate_step` | KeywordReviewCard | 重新生成 |
| `open_drawer` | RetrievalCandidateCard | 打开详情抽屉 |
| `save_candidate` | RetrievalCandidateCard | 保存候选（不直接写 Evidence Ledger） |
| `reject_candidate` | RetrievalCandidateCard | 淘汰候选 |
| `promote_to_selected` | — | 已注册，待 S23 使用 |
| `mark_needs_review` | EvidenceRefCard | 标记需要人工审核 |

**安全约束：**
- action 只能触发前端已注册 handler
- action 不允许携带 JS 字符串
- action 不允许直接写 Evidence Ledger
- action 只能产生 UI state 或请求后端固定 endpoint

---

## 4. 降级策略

| 场景 | 触发条件 | 输出 | CSS 选择器 |
|------|----------|------|-----------|
| 未知 component | `card.component` 不在 REGISTRY 且不在白名单 | `renderFallbackJSON()` — 通用 JSON 摘要卡 | `.pa-card--fallback` |
| bad props | schema 校验失败（如 keywords 传了字符串） | `renderInvalidCard()` — 安全降级卡 | `.pa-card--invalid` |
| 未知 action | `isActionAllowed()` 返回 `false` | 拒绝执行，handler 不触发 | — |
| 缺失 component | `card.component` 为 `undefined`/非 string | `renderInvalidCard("missing component")` | `.pa-card--invalid` |
| script payload | `esc()` 转义 + render_protocol 安全规则 | HTML 实体转义，不允许 `<script>`/`<style>`/`<iframe>`/`eval` | — |

**渲染管线伪代码：**

```text
renderCard(card):
  compName = card.component || card.type
  if !compName → renderInvalidCard("missing component")
  if !REGISTRY[compName] → renderFallbackJSON(card)    // 非核心白名单卡
  if schema(props).failed → renderInvalidCard(error)    // bad props
  → REGISTRY[compName].render(card)                      // 正常渲染
```

---

## 5. Playwright 测试结果

| 编号 | 名称 | 断言内容 | 结果 |
|------|------|----------|------|
| **S22-PW-1** | Registry 可用 | `window.ComponentRegistry` 存在且注册了 6 张核心卡 | **PASS** |
| **S22-PW-2** | 未知 component fallback | `renderCard({ component: 'NoSuchCard_XYZ' })` 输出 `.pa-card--fallback` | **PASS** |
| **S22-PW-3** | bad props invalid card | `KeywordReviewCard` 传非数组 keywords → `validateCard` 失败 + `renderCard` 输出 `.pa-card--invalid` | **PASS** |
| **S22-PW-4** | 未知 action 被拒 | `isActionAllowed('KeywordReviewCard', 'hack_the_planet')` → `false`; `isActionAllowed('KeywordReviewCard', 'approve_step')` → `true` | **PASS** |
| **S22-PW-5** | KeywordReviewCard 删除 | mock 流到 `awaiting_review` → 删除第一个 `.pa-kw` → 数量减 1 | **PASS** |
| **S22-PW-6** | SearchQueryPlanCard 渲染 | `renderCard` 输入 paper/dataset/repo 三组 query → 三组均出现在 HTML 中 | **PASS** |
| **S22-PW-7** | RetrievalCandidateCard 渲染 | `renderCard` 输出包含 kind/title/`save_candidate` 按钮；save/reject 不直接写 Evidence | **PASS** |
| **S22-PW-8** | S21 不回退 | rail 9 步 → mock 流暂停 keyword_review → approve 推进至 completed/approved | **PASS** |

**全部 8 项通过，0 失败。**

---

## 6. 是否影响 S21

**无回退。**

S21 Step Deck 主流程（rail 9 步、mock stream keyword gate、通过后推进）在 S22-PW-8 中完整覆盖。`step_deck.js` 中的卡片渲染逻辑收束为 `ComponentRegistry.renderCard()` 调用，行为等价。S21 的 `run_state.type` 字段通过 `card.component || card.type` 兼容处理。

---

## 7. 是否影响 S17 baseline

**无变更。**

本轮实现范围为纯前端 `component_registry.js`，未修改：
- EvidenceRef / Verification / supports 规则
- Baseline 数据文件
- 后端 API 端点
- `render_protocol.js` 的安全规则（script/style/iframe/eval 拦截保持不变）

---

## 8. S23 Prompt 协议需要遵守的组件合同

S23 及后续 Session 在构建 Prompt 协议时，必须遵守以下合同：

### 8.1 渲染入口

所有卡片渲染必须通过 `ComponentRegistry.renderCard(card)` 进入，不得在 `step_deck.js` 或其他文件中为单个组件写独立 if/else 分支。

### 8.2 卡片结构

每个卡片对象必须包含：

```json
{
  "component": "CardName",
  "id": "card_001",
  "props": { ... }
}
```

`component` 为主字段，`type` 为兼容别名。Prompt 协议生成的 LLM 响应必须在卡片 JSON 中包含 `component`（或 `type`）字段。

### 8.3 Action 白名单

action 只能使用以下注册 ID，不得发明新 action：

```text
approve_step | revise_step | regenerate_step | open_drawer |
save_candidate | reject_candidate | promote_to_selected | mark_needs_review
```

如需新增 action，必须先在 `component_registry.js` 中 `register()` 并更新 SOP。

### 8.4 安全规则

以下安全约束由 `render_protocol.js` 强制执行，Prompt 协议不得绕过：
- 不得输出 `<script>`、`<style>`、`<iframe>` 标签
- 不得在 props 中嵌入 `eval()`、`new Function()` 或 `javascript:` URI
- 所有用户可见文本必须经过 `esc()` HTML 实体转义

### 8.5 新增组件流程

若 S23 需要新增卡片类型，必须：
1. 在 `component_registry.js` 中添加 `register(name, { schema, render, actions, selector })`
2. 编写对应的 schema validator 和 render function
3. 更新 SOP 和验收报告
4. 补充 Playwright 测试

---

*报告生成日期：2026-06-21*
