# Session 43 · 面试演示模式与技术深挖控制台验收报告

## 1. 本轮目标

把 Session 42 已完成的 `Step Workbench` 包装成一个可稳定面试演示、可直接回答技术追问、可指向代码/测试/文档证据的入口，而不是继续扩业务功能。

本轮重点不是“新增一套页面”，而是：

1. 在现有工作台上叠加 `Interview Mode`
2. 提供稳定 `Demo Case`
3. 提供 `Deep Dive` 模块索引
4. 提供 `Tech Switches` 和热点标注
5. 把面试文档同步到当前真实 UI
6. 补齐测试与浏览器点击验收

## 2. 实际改动

### 2.1 前端工作台

修改文件：

- `apps/web/step_workbench.js`
- `apps/web/app.js`
- `apps/web/index.html`
- `apps/web/styles.css`

新增或调整内容：

- 新增 `Interview Mode` 增强层
- 新增 `?mode=interview` 入口
- 新增“面试演示模式（加载 Demo Case）”按钮
- 新增稳定 `Demo Case`
- 新增 `3min Demo` / `10min Demo` checklist
- 新增 `Deep Dive` 模块卡片与抽屉
- 新增 `Interview Tech Switches`
- 新增面试热点按钮，能从真实 UI 跳到讲解模块
- 新增后端状态提示
- 调整 Step 6 逻辑：演示快照不再伪装成“可真实导出”

### 2.2 文档同步

更新文件：

- `docs/interview/Project_OnePager.md`
- `docs/interview/Project_DeepDive_Index.md`
- `docs/interview/Known_Limitations_For_Interview.md`
- `docs/interview/Demo_Script_3min.md`
- `docs/interview/Demo_Script_10min.md`
- `docs/interview/Technical_Highlights.md`
- `docs/interview/Architecture_Diagram.md`

同步内容：

- 把旧 Step Deck / 旧入口叙事切到当前 `Step Workbench`
- 把 `Interview Mode`、`Demo Case`、`Deep Dive`、`Tech Switches` 写成真实入口
- 明确 `implemented / lightweight / design-only` 的当前口径
- 把 Step 6 后端依赖和 Demo Case 固定数据写成诚实边界

### 2.3 测试

新增文件：

- `apps/web/e2e/test_one_topic_session43_interview_mode.py`

覆盖点：

1. 普通模式下不显示 `Interview Shell`
2. `?mode=interview` 可打开面试增强层
3. Demo Case 可加载到稳定可讲状态
4. RAG Deep Dive 可打开，且包含代码 / 测试 / 文档路径
5. checklist 可联动高亮导出区

## 3. 验收结果

### 3.1 Playwright E2E

执行命令：

```powershell
.venv\Scripts\python.exe -m pytest apps\web\e2e\test_one_topic_session42_workbench_chat_edit.py apps\web\e2e\test_one_topic_session43_interview_mode.py -q
```

结果：

- `10 passed in 23.39s`

说明：

- Session 42 的对话式编辑能力未回归
- Session 43 的面试增强层已通过基础浏览器验收

### 3.2 浏览器点击验收

使用浏览器点击确认：

1. 打开 `http://127.0.0.1:18182/?mode=interview`
2. 点击“面试演示模式（加载 Demo Case）”
3. 确认出现 Demo Case 提示
4. 确认 Step 6 文案为：

> `Step 1-5 已完成，但当前只是演示快照；真实导出需要先绑定后端 project。`

5. 点击 `RAG` Deep Dive 卡片
6. 确认抽屉中出现：
   - `apps/api/app/services/rag_pipeline.py`
   - `apps/web/e2e/test_one_topic_session34_rag_eval.py`
   - `docs/interview/RAG_Design_Explainer.md`

截图文件：

- `session43-interview-demo.png`

### 3.3 Step 6 导出 smoke

执行链路：

1. `POST /api/v1/one-topic/analyze`
2. `POST /api/v1/one-topic/{project_id}/final-package/build`

结果：

```json
{
  "project_id": "ot_ba5cbd8f4088",
  "analyze_elapsed_sec": 16.21,
  "has_markdown": true,
  "template_key": "default",
  "citation_count": 5,
  "char_count": 2932
}
```

结论：

- 后端 `18181` 当前可用
- Step 6 后端构建链路至少有一次真实 smoke 成功
- 演示模式中的 Demo Case 不再误导成“已经具备真实导出上下文”

## 4. 工作流程

本轮实际执行流程如下：

1. 先复核 Session 42 的真实 UI、文档和后端状态
2. 识别出最小风险路径：不造第二套页面，只给 `Step Workbench` 加面试增强层
3. 实现 `Interview Mode`、`Demo Case`、`Deep Dive`、`Tech Switches`、热点标注
4. 同步 `docs/interview`，让文档与真实 UI 对齐
5. 跑 Session 42/43 的前端 E2E
6. 做浏览器点击验收
7. 跑 Step 6 后端构建 smoke
8. 收束为本报告

## 5. 本轮技术判断

### 采用方案

在现有 `Step Workbench` 上增量叠加 `Interview Mode`

原因：

- 回归风险最小
- 文档和 UI 更容易长期保持一致
- 面试层不接管业务状态，只做讲解增强

### 放弃方案

单独新做一套面试页

原因：

- 会快速与真实工作台分叉
- 测试成本和维护成本更高
- 更容易出现“讲稿能讲，真实 UI 对不上”的问题

## 6. 当前边界

1. Demo Case 是固定演示数据，不代表实时联网检索
2. Step 6 真实导出仍依赖后端 project
3. `LangGraph runtime`、`SubAgent Router`、部分 `MCP` 入口仍是 `design-only`
4. 面试模式是增强层，不是新的业务状态机

## 7. 关于 MiniMax 子代理

本轮按要求优先尝试 MiniMax 路线，但本机 MiniMax CLI 仍不可用，原因是本地可执行路径失效，无法正常拉起子代理。

因此本轮改为由主代理直接完成：

- 实现
- 测试
- 浏览器点击验收
- 报告整理

没有把“子代理已验证”写成通过项。

## 8. 通过结论

Session 43 本轮可判定为：

- `Interview Mode` 已落地
- `Demo Case` 已可稳定加载
- `Deep Dive` 已覆盖核心面试模块
- `Tech Switches` 已区分 on / off / design-only
- `docs/interview` 已同步到当前真实工作台
- Session 42/43 相关前端 E2E 已通过
- Step 6 后端构建 smoke 已通过

整体结论：

> 可以进入“面试演示入口已具备、后续继续补深挖内容或扩大自动化覆盖”的状态。
