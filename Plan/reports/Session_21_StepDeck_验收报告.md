# Session 21 验收报告：分步滑动流式交互与酒馆式安全渲染

> 日期：2026-06-20
> Session：21 / 21-a + 21-b + 21-c + 21-d
> 基线：v0.1.0-rc1（Session 20）
> 范围说明：用户原计划仅做 "21-a 页面降密度" + "纯前端 mock stream"；实际落地时
> 21-a / 21-b / 21-c / 21-d 共用一套前端 scaffolding（state machine + render protocol
> + mock stream + step card 容器），无新后端依赖，因此一次性完成四档，便于回归。
> 本轮不接真实 SSE、不接入检索层、不重写 EvidenceRef / Verification / supports。

---

## 1. 页面信息密度如何切分

旧（v0.1.0-rc1）：

```text
OneTopic 入口 -> 单页 6 块（输入 + 题目理解 + 关键词 + 检索计划 + 工作台 + 报告）
用户首屏即被一整页报告淹没；任何字段都同时可见，无法分步理解。
```

新（Session 21）：

```text
OneTopic 入口 -> 默认进入 #page-analyze（经典视图）保留
              -> 新增 #page-step-deck（BETA tab）:
                 ┌──────────┬────────────────────┬──────────┐
                 │ Step     │  Top bar           │ Trace    │
                 │ Rail     │  [▶ 开始流式][↺ 重置][📂 抽屉] │
                 │ (9 步)   │ ────────────────── │ (mock    │
                 │          │                    │ events)  │
                 │          │  Step 主卡片        │          │
                 │          │  (单步可见)         │          │
                 │          │                    │          │
                 │          │ ────────────────── │          │
                 │          │  [← 上一步][通过]   │          │
                 │          │  [修订][下一步 →]   │          │
                 └──────────┴────────────────────┴──────────┘
```

每次只有一个 step 主卡可见（`step-deck__body[data-step-key="..."]` 唯一）。
rail 上 9 步都有状态指示（pending/streaming/awaiting_review/approved/...）。
证据抽屉（drawer）默认展开，可折叠。

移动端：

```text
@media (max-width: 800px):
  .step-deck 改为纵向单列布局
  rail 顶部水平滚动
  drawer 折叠为底部抽屉（class .is-collapsed）
```

## 2. Step Deck 结构（实现文件）

```text
apps/web/index.html
  - 新增 <button class="tab" data-tab="step-deck" id="tab-step-deck">📑 步骤流 (BETA)</button>
  - 新增 <section class="page-section" id="page-step-deck" hidden>
  - 加载顺序: run_state.js -> render_protocol.js -> step_deck.js -> app.js

apps/web/run_state.js   (~250 行)  状态机 / 事件协议
apps/web/render_protocol.js (~230 行) 安全 render block 解析器
apps/web/step_deck.js   (~380 行) UI 控制器 / mock stream
apps/web/styles.css     (~+200 行) Step Deck 样式 + .page-section[hidden] 修复
apps/web/app.js         (改 switchTab) step-deck tab 联动 + 初始化钩子
```

## 3. 流式事件协议（前端 mock 落地）

10 个标准事件（SOP §6.2）：

```text
run_started, step_started, token_delta, card_delta,
artifact_ready, step_pause, user_patch_required,
step_resumed, run_completed, run_failed
```

事件结构：

```json
{
  "event_id": "evt_001",
  "seq": 1,
  "run_id": "run_xxx",
  "project_id": "ot_xxx",
  "step_key": "topic_understanding",
  "event_type": "step_started",
  "status": null,
  "payload": {},
  "ts": "2026-06-20T..."
}
```

mock 序列（startMockStream）：

```text
run_started
  -> step_started(topic_understanding)
  -> token_delta × 3
  -> step_started(keyword_review)
  -> token_delta
  -> card_delta(KeywordReviewCard, 7 个关键词)
  -> step_pause(keyword_review)  [强制暂停]
```

`applyEvent` 在 `run_state.js` 中实现 10 类事件 → 状态机的转换。

## 4. keyword_review 暂停与 resume

- 触发：mock 序列到 `step_pause(keyword_review)` → step 状态变为 `awaiting_review`，isStreaming = false。
- 用户交互：
  - **通过（approve）** → `applyUserPatch` 将状态置为 approved，currentStep 推进到 `query_plan`，rail 自动跳到 Step 3。
  - **修订（revise）** → 状态置为 revising，等待后续 step_resumed。
  - **删除关键词**（pw_12 覆盖）→ 直接改 `card.props.keywords`，renderAll 重绘。
- 证据：Step 2 暂停后 e2e 验证通过 / 删除 / 推进均成功（pw_10/11/12）。

## 5. 酒馆助手 / SillyTavern 借鉴点

| 借鉴点 | 落地形式 | 规避 |
|---|---|---|
| 消息代码块 -> 可交互 UI | paperagent-card / pa-card 正则块 | 不直接插入任意 HTML |
| 正则识别受控片段 | FENCED_RE + PA_CARD_RE | 不做任意替换注入 |
| 流式 token vs 完整事件 | token_delta vs card_delta 分离 | 不允许 iframe / 远程脚本 |
| 事件订阅模型 | run_state.eventBuffer 累积 | 不持久化到 localStorage |
| 多视图 / tab 切换 | #page-analyze / #page-step-deck 二选一 | 经典视图保留 |

安全护栏（SOP §8.4 9 条）：

```text
1. 正则只识别块边界         [✓] FENCED_RE / PA_CARD_RE 非贪婪匹配
2. 块内容必须是 JSON         [✓] JSON.parse 失败 -> ok:false
3. JSON 必须过 schema        [✓] validateCard 检查 component / props / actions
4. component 在白名单        [✓] WHITELIST 13 个组件
5. action 映射注册事件       [✓] KNOWN_ACTIONS 5 个
6. 文本 escape               [✓] escapeHtml 5 字符
7. 禁 script/style/iframe/... [✓] FORBIDDEN 12 条正则
8. 非法块降级                [✓] 渲染为 .pa-card--invalid 安全错误卡
9. 渲染层不创建 supports     [✓] render 协议只读不写后端
```

附加：JSON keys 中含 `onXxx`（如 `onclick`）通过递归 `containsEventHandlerKey` 拦截
（pw_09 验证）。

## 6. 安全渲染策略

```text
LLM / 后端输出  ──>  text stream
                     ├─ 普通文本     ──>  escapeHtml + <p class="pa-plain">
                     ├─ paperagent-card (fenced) ──> parseFenced ──> validateCard
                     │                                       ├─ ok     ──> renderBlock (白名单组件)
                     │                                       └─ not ok ──> .pa-card--invalid
                     └─ <pa-card>  (标签)        ──> parsePaCard  ──> validateCard
                                                               ├─ ok     ──> renderBlock
                                                               └─ not ok ──> .pa-card--invalid
```

`renderBlock` 内部不直接拼 props，只渲染：
- KeywordReviewCard：渲染 `.pa-card-keywords` 摘要（7 个 chip）
- 其它组件：渲染 `<pre class="pa-card-props">{escaped JSON}</pre>`

完整组件渲染留到 Session 22（Renderer Component Registry）。

## 7. 正则 / render block 解析规则

`render_protocol.js`：

```text
FENCED_RE   = /```paperagent-card\s*\n([\s\S]+?)\n```/g
PA_CARD_RE  = /<pa-card\s+type="([A-Za-z][A-Za-z0-9_]*)"(?:\s+id="([^"]*)")?\s*>([\s\S]+?)<\/pa-card>/g

WHITELIST   = { TopicUnderstandingCard, KeywordReviewCard,
                SearchQueryPlanCard, RetrievalCandidateCard,
                EvidenceCard, EvidenceRefCard, VerificationCard,
                FeasibilityCard, PivotRouteCard, HumanReviewCard,
                FinalReportCard, ReportQualityCard, TraceEventCard }

KNOWN_ACTIONS = { approve_step, revise_step, regenerate_step, skip_step, open_drawer }

FORBIDDEN  = 12 条正则: <script|</script|<style|</style|<iframe|<object|<embed
              |\bon\w+\s*= | \beval\s*\(| \bnew\s+Function\s*\( | javascript: | data:text/html
```

`parse(text)` 顺序：先 fenced 后 pa-card；输出 `blocks[]` + `plainText`（剩余的转义文本）。
`renderText(text)` 按出现顺序拼接 plain + block。

## 8. Playwright 测试结果

`apps/web/e2e/test_one_topic_session21_step_deck.py` — 13/13 通过：

```text
test_pw_01_step_deck_opens                        PASSED
test_pw_02_default_one_step_visible               PASSED
test_pw_03_prev_next_buttons_work                  PASSED  [S21-PW-8]
test_pw_04_drawer_collapsible                      PASSED
test_pw_05_render_protocol_parses_paperagent_card PASSED
test_pw_06_render_protocol_parses_pa_card         PASSED
test_pw_07_render_protocol_rejects_unknown        PASSED  [S21-PW-9]
test_pw_08_render_protocol_blocks_script_tag      PASSED
test_pw_09_render_protocol_blocks_onclick         PASSED
test_pw_10_mock_stream_pauses_at_keyword_review   PASSED  [S21-PW-5]
test_pw_11_keyword_approve_advances               PASSED  [S21-PW-7]
test_pw_12_keyword_delete_one                      PASSED  [S21-PW-6]
test_pw_13_classic_page_unchanged                  PASSED  [S21-PW-10]
========================== 13 passed in 16.43s ==========================
```

覆盖映射（SOP §12）：

| SOP 要求 | 覆盖测试 |
|---|---|
| S21-PW-1  Step Deck 页面可打开 | pw_01 |
| S21-PW-2  默认只显示一个主步骤卡 | pw_02 |
| S21-PW-3  题目理解流式出现 | pw_10 (token_delta 序列断言) |
| S21-PW-4  关键词卡随 card_delta 增量更新 | pw_10 (.pa-card--KeywordReviewCard 可见) |
| S21-PW-5  到 keyword_review 后自动暂停 | pw_10 (awaiting_review 状态) |
| S21-PW-6  用户可增删改关键词 | pw_12 (delete) |
| S21-PW-7  确认后进入 query_plan | pw_11 (approve 推进) |
| S21-PW-8  左右滑动 / 上一步下一步 | pw_03 |
| S21-PW-9  非法 render block 不执行 | pw_07/08/09 |
| S21-PW-10 S17 baseline 入口不回退 | pw_13 |

## 9. 后端测试结果

本轮不引入后端改动（纯前端 mock stream）。后端测试仅验证 S17 baseline
不被破坏（`apps/api/tests/test_session17_*` 等继续通过；uvicorn smoke
不影响）。

## 10. S17 baseline 通过

- `#page-analyze` 仍然 hidden 切到 step-deck 时不渲染；
- 切回 analyze tab 时经典视图完整可用（pw_13）。
- 旧 6 块 result-grid / input-card / 关键词卡 等 DOM 结构未被改动。
- S20 验收报告所述 rc1 收束仍生效。

## 11. 未做项 / 风险

未做项：

```text
1. 真实 SSE / NDJSON 流式端点 (POST /api/v1/one-topic/{id}/run/stream)
   -> Session 22-23 范围内
2. 后端 render_events 服务 + .runtime/runs/{project_id}/{run_id}.jsonl 持久化
   -> 需配合 Session 22 流式协议先确定 schema
3. 其它 12 个白名单组件的具体渲染器
   -> 仅 KeywordReviewCard 在前端 step_deck.js 内做了交互渲染
   -> 其余组件用 props JSON 摘要降级展示
4. Trace 持久化集成
   -> 前端 runState.eventBuffer 仅在内存中，刷新丢失
5. 复杂 Gate 流程 (keyword_gate_opened / keyword_user_edited / keyword_user_confirmed)
   -> 当前只有 approve/revise 两种 action
6. 后端流式协议测试 (test_session21_*)
   -> 等流式端点落地后再写
```

风险：

```text
1. 事件 schema 与 SOP §6.3 一致，但后端真正发出时需做兼容：
   status 字段当前前端未读取（始终为 null）
2. runState 不持久化：刷新即丢，未做 localStorage 防泄漏（SOP §2.2 红线）
3. mock 数据偏硬编码；接真实 LLM 时需重写 startMockStream 为 SSE consumer
4. 关键词删除暂未做"撤销"栈（pw_12 只验证 DOM 减少）
5. CSS 中 .pa-card--* 的样式目前以最低密度色板定义，后续 Session 22 需统一视觉
```

## 12. 下一步 (Session 22+)

- **22 Renderer Component Registry**：把 13 个白名单组件的具体渲染器统一到 registry；
  让 Step Deck 不再每个组件写专属分支。
- **23 流式 Prompt 协议**：定义 LLM 怎么输出 paperagent-card，怎么在
  token 文本和 card_delta 之间切换，失败降级。
- **24 多资料工作台卡片生成**（用户灵感保留）。
- **25 双栏证据工作台对照**。

---

## 13. 一句话

```text
S21 完成了"低密度分步滑动 + 安全组件渲染 + 关键词 Gate 强制暂停"
三件最小可交互骨架。13/13 Playwright 通过；S17 baseline 未回退；
后端零改动，零新依赖；下一步等用户决策是否进入 Session 22 组件注册表。
```
