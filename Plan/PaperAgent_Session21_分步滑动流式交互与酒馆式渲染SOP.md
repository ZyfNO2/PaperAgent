# PaperAgent Session 21 / H1 SOP：流式步骤卡与酒馆式交互渲染

> 日期：2026-06-20  
> 阶段定位：Session 20 已收束为 `0.1.0-rc1`。Session 21 是新方向的第一步，不做后续复杂 Agent 化，先把“传进去 -> 选题 -> 关键词拆解 -> 暂停审查”的主线变成人性化、低密度、可测试的交互流程。  
> 本轮目标：把 OneTopic 从单页高密度报告改为分步滑动 Step Deck；LLM / 后端以流式事件输出；前端边接收边渲染安全交互卡；在关键词拆解后默认暂停，等待用户审查和调整。

---

## 1. 本轮结论

已审阅当前报告链：

```text
Plan/reports/Session_17_Demo_Baseline_验收报告.md
Plan/reports/Session_18_Error_Observability_验收报告.md
Plan/reports/Session_19_Report_Templates_验收报告.md
Plan/reports/Session_20_Release_Candidate_验收报告.md
```

判断：

```text
Session 20 已完成 v0.1.0-rc1 收束；
Session 21 可以进入“交互方式重构”；
但本轮必须严格保护 S17 demo baseline、Evidence Ledger、Verification、Trace、ReportQuality。
```

本轮不是重写业务逻辑，而是把已有流程包装成：

```text
步骤化状态机 + 流式事件 + 安全组件渲染 + 人工审查 Gate
```

---

## 2. 参考资料吸收

### 2.1 CrackAgent H1 SOP

参考文件：

```text
G:/Zed/CrackAgent/doc/sop/ch5/H1-流式步骤卡与酒馆式交互渲染_SOP.md
```

吸收点：

```text
1. 从长报告改为 StepFlow / Step Deck；
2. 左侧步骤导航，中间主步骤卡，右侧证据抽屉；
3. SSE 事件采用 run_started / step_started / token_delta / card_delta / artifact_ready / step_pause / user_patch_required / step_resumed / run_completed / run_failed；
4. 前端 StepRunState 使用 pending / streaming / awaiting_review / approved / revising / completed / failed；
5. 渲染块采用白名单组件协议，不执行任意 JS；
6. Playwright 要覆盖“流式出现、关键词暂停、用户编辑、继续执行、非法块降级”。
```

PaperAgent 改名适配：

```text
CrackAgent 的 crack-card 只作为参考；
PaperAgent 正式协议使用 pa-card / paperagent-card；
如需导入参考示例，可临时兼容 crack-card，但不能作为长期公开协议。
```

### 2.2 酒馆助手 / SillyTavern

已补充参考页面：

```text
酒馆助手介绍：
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/关于酒馆助手/介绍.html

酒馆助手渲染器：
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/基本用法/渲染器.html

酒馆助手正则：
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/功能详情/酒馆正则/获取正则.html
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/功能详情/酒馆正则/创建和修改正则.html

酒馆助手请求生成 / 流式事件：
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/功能详情/请求生成.html

酒馆助手事件：
https://n0vi028.github.io/JS-Slash-Runner-Doc/guide/功能详情/监听和发送事件.html

SillyTavern 官方文档：
https://docs.sillytavern.app/
```

可借鉴点：

```text
1. “消息代码块 -> 可交互 UI”的渲染思路；
2. 通过正则识别 AI 输出中的受控片段；
3. 流式生成时区分完整文本事件和增量 token 事件；
4. eventOn / eventOnce / eventMakeFirst / eventMakeLast 这类事件订阅模型；
5. 多模型、后台生成、工具调用、图片输入等扩展空间。
```

必须规避：

```text
1. 酒馆助手允许 iframe / script 执行，PaperAgent 本轮不能照搬；
2. LLM 输出不得直接成为 HTML / JS 并插入主页面；
3. 不允许 eval / new Function / onClick 字符串 / 远程脚本加载；
4. 不允许模型输出读取 localStorage、API key、聊天记录、文件系统；
5. 正则只做块识别，不做任意替换注入。
```

PaperAgent 的正确吸收方式：

```text
酒馆式“可交互渲染体验”可以学；
酒馆式“任意脚本执行能力”不能学；
最终落地为安全 DSL + 组件白名单 + schema 校验 + 固定 action 映射。
```

### 2.3 `C:/Users/ZYF/Desktop/Test.txt`

只吸收工程形态：

```text
1. 固定外壳；
2. 多视图 / tab / list-detail；
3. 可折叠容器；
4. modal 弹窗；
5. 状态对象驱动 UI；
6. 局部按钮和交互面板。
```

不吸收：

```text
成人向内容、敏感字段、密钥逻辑、任意脚本注入、不可审查的外部依赖。
```

---

## 3. Session 21 目标

一句话：

```text
把“一页报告”改成“逐步滑动的流式 Agent 工作台”，第一处强制暂停在关键词拆解页。
```

用户主线：

```text
输入题目：基于 YOLO 的 XXX 检测
-> Step 1：题目理解
-> Step 2：关键词拆解：YOLO / 检测 / XXX
-> 暂停：请用户审查、增删、改类型
-> 用户确认
-> Step 3：检索计划
-> Step 4：论文 / 数据集 / 工程候选
-> Step 5：可行性判断
-> Step 6：开题报告推荐
-> Step 7：低门槛模拟审稿 / 初步审核
```

本轮最小可交付只要求跑通到：

```text
输入题目 -> 流式题目理解 -> 流式关键词卡 -> 暂停审查 -> 用户修改/确认 -> 可继续进入检索计划占位页
```

---

## 4. 本轮不做什么

| 不做 | 原因 |
|---|---|
| 不重写 EvidenceRef / Verification / supports 硬规则 | 保持 S17 baseline |
| 不做真实全文 RAG 大改 | 本轮目标是交互层和流式层 |
| 不接入任意第三方脚本执行 | 安全风险太高 |
| 不做完整 SillyTavern clone | 只借鉴渲染、正则、事件思想 |
| 不做插件市场 | 后续 Session 再扩展 |
| 不把所有证据工作台一次性重排完 | 先跑通选题 MVP 主线 |

---

## 5. UI 信息架构

### 5.1 Step Deck 总体布局

```text
左侧：Step Rail / 当前状态 / 审查点
中间：当前 Step 主卡片，可左右滑动
右侧：Evidence Drawer / Trace / Raw JSON / 引用详情，可折叠
底部：确认、修改、重跑、继续、回退
```

移动端：

```text
顶部 Step Indicator；
中间单卡片；
证据抽屉变为底部抽屉；
左右滑动使用 scroll-snap。
```

桌面端：

```text
左侧窄导航；
中间主面板；
右侧可折叠辅助面板；
按钮使用固定 action，而不是模型生成 onclick。
```

### 5.2 Step 列表

```text
Step 0：输入题目 / 上传材料
Step 1：题目理解
Step 2：关键词审查 Gate
Step 3：检索计划
Step 4：候选证据：论文 / 数据集 / 工程
Step 5：证据工作台
Step 6：可行性与 Pivot
Step 7：开题报告推荐
Step 8：低门槛委员会复核 / ReportQuality
```

状态：

```text
pending
streaming
awaiting_review
approved
revising
completed
failed
```

默认暂停点：

```text
Step 2 keyword_review 必须暂停；
用户未确认前，不自动进入真实检索和可行性判断。
```

---

## 6. 流式事件协议

### 6.1 推荐端点

```text
POST /api/v1/one-topic/{project_id}/run/stream
POST /api/v1/one-topic/{project_id}/run/resume
GET  /api/v1/one-topic/{project_id}/run/{run_id}/events
```

MVP 可接受：

```text
1. SSE: text/event-stream；
2. NDJSON: application/x-ndjson；
3. 前端 mock stream，用于先跑 Playwright。
```

### 6.2 标准事件

优先使用 H1 对齐事件名：

```text
run_started
step_started
token_delta
card_delta
artifact_ready
step_pause
user_patch_required
step_resumed
run_completed
run_failed
```

PaperAgent 内部可保留兼容别名：

```text
card_patch      -> card_delta
gate_required   -> step_pause + user_patch_required
run_paused      -> step_pause
error           -> run_failed
```

### 6.3 事件格式

```json
{
  "event_id": "evt_001",
  "seq": 1,
  "run_id": "run_001",
  "project_id": "ot_001",
  "step_key": "keyword_review",
  "event_type": "card_delta",
  "status": "streaming",
  "payload": {},
  "ts": "2026-06-20T20:00:00+08:00"
}
```

要求：

```text
1. seq 单调递增；
2. 同一 run 可 replay；
3. 断流后可通过 events 端点回放；
4. step_pause 必须带 reason 和 available_actions；
5. 用户修改必须生成 user_patch_applied / trace 记录。
```

---

## 7. 前端状态机

```ts
type StepStatus = 'pending' | 'streaming' | 'awaiting_review' | 'approved' | 'revising' | 'completed' | 'failed'

type StepCard = {
  stepId: string
  title: string
  status: StepStatus
  textBuffer: string
  componentBlocks: RenderBlock[]
  artifacts: ArtifactRef[]
  userPatch?: Record<string, unknown>
}
```

建议状态：

```js
const runState = {
  runId: null,
  currentStep: 'input',
  steps: {},
  cards: {},
  gates: {},
  eventBuffer: [],
  lastSeq: 0
}
```

核心函数：

```text
startStreamingRun(payload)
consumeRunStream(response)
applyRunEvent(evt)
renderStepDeck()
renderComponentCard(card)
openGate(gate)
submitGateAction(actionId, payload)
resumeRun(gatePayload)
replayRunEvents(runId)
```

---

## 8. 酒馆式安全渲染协议

### 8.1 Canonical Render Block

LLM / 后端可以输出结构化渲染块，但必须过 schema：

```json
{
  "type": "render_block",
  "component": "KeywordReviewCard",
  "id": "kw_001",
  "props": {
    "keywords": [
      {"kind": "method", "text": "YOLO"},
      {"kind": "task", "text": "检测"},
      {"kind": "object", "text": "XXX"}
    ],
    "editable": true
  },
  "actions": [
    {"id": "approve", "event": "approve_step"},
    {"id": "edit", "event": "revise_keywords"}
  ]
}
```

### 8.2 白名单组件

```text
UploadSummaryCard
TopicUnderstandingCard
KeywordReviewCard
SearchQueryPlanCard
RetrievalCandidateCard
EvidenceCard
EvidenceRefCard
VerificationCard
FeasibilityCard
PivotRouteCard
HumanReviewCard
FinalReportCard
ReportQualityCard
TraceEventCard
```

### 8.3 受控文本块

PaperAgent 正式支持两种块：

````text
```paperagent-card
{ "component": "KeywordReviewCard", "props": {} }
```
````

```html
<pa-card type="KeywordReviewCard" id="kw_001">
{ "props": {} }
</pa-card>
```

兼容导入：

```text
crack-card 只用于读取 H1 示例；新代码、新 prompt、新测试统一写 paperagent-card / pa-card。
```

### 8.4 安全规则

```text
1. 正则只识别块边界；
2. 块内容必须是 JSON；
3. JSON 必须过 schema；
4. component 必须在白名单；
5. action 必须映射到前端已注册事件；
6. 文本必须 escape；
7. 禁止 script / style / iframe / onClick / eval / new Function；
8. 非法块降级为普通文本或安全错误卡；
9. 渲染层不能直接创建 supports 或 core evidence。
```

---

## 9. 关键词 Gate 流程

默认流程：

```text
run_started
-> step_started(topic_understanding)
-> token_delta / card_delta
-> step_completed(topic_understanding)
-> step_started(keyword_review)
-> token_delta / card_delta
-> step_pause(keyword_review)
-> user_patch_required(keyword_review_gate)
-> 用户编辑 / 确认
-> step_resumed
-> step_started(query_plan)
```

关键词卡必须支持：

```text
1. 新增关键词；
2. 删除关键词；
3. 修改关键词文本；
4. 修改关键词类型：method / task / object / domain / dataset / metric / constraint；
5. 重新拆解；
6. 确认并继续。
```

Trace 必须记录：

```text
keyword_gate_opened
keyword_user_edited
keyword_user_confirmed
keyword_regenerated
run_resumed
```

---

## 10. 代码落地建议

### 10.1 前端建议文件

如果当前前端仍偏单文件，先低风险分区；若已有模块化结构，再拆文件：

```text
apps/web/app.js
apps/web/styles.css
apps/web/index.html
```

可选拆分：

```text
apps/web/step_deck.js
apps/web/stream_renderer.js
apps/web/render_protocol.js
apps/web/run_state.js
```

不强制一次性组件化，避免破坏 RC1。

### 10.2 后端建议文件

```text
apps/api/app/services/streaming.py
apps/api/app/services/render_events.py
apps/api/app/schemas_streaming.py
```

持久化建议：

```text
.runtime/runs/{project_id}/{run_id}.jsonl
.runtime/runs/{project_id}/{run_id}.state.json
```

概念边界：

```text
Streaming Event：给 UI 的过程事件；
Trace Event：给审计和复盘的操作记录；
EvidenceRef：给证据链的事实引用；
三者可以互相引用，但不能混成同一个对象。
```

---

## 11. 分步执行

### 21-a 页面降密度

任务：

```text
1. 新增 Step Deck 容器；
2. 先用 mock step 数据；
3. 每次只显示一个主步骤；
4. 增加左右滑动 / 上一步 / 下一步；
5. 右侧证据抽屉可折叠。
```

验收：

```text
进入 OneTopic 后不再默认看到一整页高密度报告；
用户默认只看到当前步骤主卡；
可回看前一步；
未过 Gate 时后续步骤只可预览不可执行。
```

### 21-b 流式事件 MVP

任务：

```text
1. 新增 mock stream 或真实 SSE；
2. 输出 run_started / step_started / token_delta / card_delta / step_pause；
3. 前端边接收边更新文本和卡片；
4. 到 keyword_review 自动暂停。
```

验收：

```text
题目理解文本分块出现；
关键词卡逐步出现；
到关键词页状态变为 awaiting_review；
不会自动进入检索计划。
```

### 21-c KeywordReviewCard

任务：

```text
1. 展示 YOLO / 检测 / XXX 这类 method-task-object 拆解；
2. 支持增删改；
3. 支持确认并继续；
4. 用户 patch 写入 Trace；
5. resume 后进入 query_plan 占位页。
```

验收：

```text
用户能修改关键词；
修改后 UI 状态为 revising 或 approved；
确认后进入 query_plan；
Trace 中能看到用户编辑记录。
```

### 21-d paperagent-card 解析器

任务：

```text
1. 支持 fenced paperagent-card；
2. 支持 <pa-card>；
3. 支持 schema 校验；
4. 非白名单组件降级；
5. script/onClick/iframe 不执行。
```

验收：

```text
合法 KeywordReviewCard 可渲染；
非法 component_type 显示安全降级；
恶意 script/onClick 不执行；
解析失败不影响普通文本流式显示。
```

---

## 12. Playwright 测试要求

新增或扩展：

```text
apps/web/e2e/test_one_topic_session21_stepflow_streaming.py
```

必须覆盖：

```text
S21-PW-1：Step Deck 页面可打开；
S21-PW-2：默认只显示一个主步骤卡；
S21-PW-3：点击开始后题目理解流式出现；
S21-PW-4：关键词卡随 card_delta 增量更新；
S21-PW-5：到 keyword_review 后自动暂停；
S21-PW-6：用户可增删改关键词；
S21-PW-7：确认后进入 query_plan；
S21-PW-8：左右滑动 / 上一步下一步可用；
S21-PW-9：非法 render block 不执行脚本；
S21-PW-10：S17 demo baseline 入口不回退。
```

后端测试：

```text
apps/api/tests/test_session21_stepflow_streaming.py
apps/api/tests/test_session21_render_protocol.py
apps/api/tests/test_session21_keyword_gate.py
```

必须覆盖：

```text
1. 事件顺序正确；
2. keyword_review 后暂停；
3. 未确认 Gate 不能进入 retrieval；
4. resume 后继续；
5. jsonl 可 replay；
6. 非法 component 被拒绝；
7. script/html payload 被转义；
8. Trace 写入用户操作；
9. S17 baseline 继续通过。
```

---

## 13. 验收标准

Session 21 通过条件：

```text
1. OneTopic 页面信息密度被切分为 Step Deck；
2. 默认流程按步骤推进；
3. LLM / mock LLM 输出可流式显示；
4. 关键词拆解卡可边流式边渲染；
5. keyword_review 后必须暂停；
6. 用户可审查、编辑、确认关键词；
7. 确认后可继续到 query_plan；
8. paperagent-card / pa-card 可被安全解析；
9. 非法 JS / HTML 不执行；
10. Gate 操作写入 Trace；
11. 不破坏 EvidenceRef / Verification / supports；
12. S17 baseline 继续通过；
13. 新增后端测试通过；
14. 新增 Playwright 测试通过；
15. 新增 Session21 验收报告。
```

---

## 14. 完工报告要求

完成后新增：

```text
Plan/reports/Session_21_StepFlow_Streaming_Renderer_验收报告.md
```

报告必须写：

```text
1. 页面信息密度如何切分；
2. Step Deck 结构截图或说明；
3. 流式事件协议；
4. keyword_review 暂停与 resume；
5. 酒馆助手 / SillyTavern 借鉴点；
6. 安全渲染策略；
7. 正则块 / render block 解析规则；
8. Playwright 测试结果；
9. 后端测试结果；
10. S17 baseline 是否通过；
11. 未做项和风险。
```

---

## 15. 后续 Session 预留

Session 22：Renderer Component Registry 与交互卡片库

```text
把 KeywordReviewCard / EvidenceCard / MaterialCard / QualityCard 等沉淀为稳定组件注册表，支持统一 schema、统一 action、统一降级。
```

Session 23：流式 Prompt 协议与工具调用边界

```text
定义 LLM 如何输出 paperagent-card，如何在 token 文本和结构化 card_delta 之间切换，如何失败降级。
```

Session 24：多资料上传的工作台卡片生成

```text
保留用户灵感：左侧放用户指定论文/数据集/工程，右侧放系统检索到的候选；Agent 可根据网页链接、图片、文字描述生成卡片放进工作区。
```

Session 25：证据工作台双栏对照与人工编排

```text
把“我想用的资料”和“系统找到的资料”做成左右对照，支持拖拽、收藏、淘汰、标记核心证据。
```

---

## 16. 一句话提醒

```text
本轮最重要的不是把系统做得更“炫”，而是让用户不再被一整页报告淹没：每次只判断一步，系统流式生成，关键处停下来等人确认。
```
