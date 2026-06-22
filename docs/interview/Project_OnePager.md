# PaperAgent · 面试演示版项目一页纸

## 项目定位

PaperAgent 是一个面向“毕业论文开题判断”的 Agent 工作台。它不把问题简化成聊天框，而是把“题目理解 -> 关键词拆解 -> 候选证据 -> 可行性判断 -> 开题建议 -> 导出前检查”拆成可确认、可回看、可修改的工作流。

## 当前主入口

当前真实前端入口是 `apps/web/index.html` 对应的浏览器页面：

- 普通模式：输入题目后进入 `Step Workbench`
- 面试模式：`?mode=interview` 或“面试演示模式（加载 Demo Case）”

面试模式不是第二套产品，而是在同一套工作台上叠加：

- 稳定 `Demo Case`
- 3 分钟 / 10 分钟讲解脚本
- Deep Dive 模块索引
- Tech Switches 矩阵
- 关键热点标注

## 真实可演示闭环

当前前端主闭环是 5 个步骤加 1 个导出区：

1. 题目理解
2. 关键词拆解
3. 检索计划与候选证据
4. 可行性判断
5. 开题建议
6. Step 6 导出区

其中：

- 左栏是 `LLM 思维 / 对话`
- 中栏是分步工作台
- 右栏是 `证据 Trace`
- 写操作先生成 `WorkspaceCommand` 预览，再由用户确认
- 一旦前序被修改，后续步骤会被标记为 `stale`

## 为什么这版适合面试

这版项目可以直接回答面试中的四类高频问题：

1. 你的 Agent 不是 PPT 吗？
2. 用户修改后系统怎么保证可追溯？
3. RAG / Memory / MCP / Agent 架构在哪里能看到？
4. 哪些已经实现，哪些只是设计预留？

因为这些入口已经被做成同一套 UI 里的可点击对象，而不是散落在不同文档里。

## 技术亮点

### 1. Human-in-the-loop Workflow

- 不是一次性吐完整报告
- 每步都有 Gate
- 支持重跑与回看

### 2. 对话式编辑不直接改状态

- 讨论模式只回答，不改数据
- 建议模式只生成预览，不直接写入
- 用户确认后才真正落地

### 3. Trace / Memory 讲解入口前置

- 用户确认
- 修改记录
- stale 传播
- Demo Case 恢复

这些都能在前端现场看到，不必临时翻后端日志。

### 4. 面试模式区分 implemented / lightweight / design-only

- `Workflow / Evidence / Tests`：偏 implemented
- `RAG / Memory`：偏 lightweight
- `LangGraph runtime / SubAgent Router / MCP 深挖`：design-only 或预留

## 关键文件

- `apps/web/step_workbench.js`
- `apps/web/app.js`
- `apps/web/index.html`
- `apps/web/styles.css`
- `apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py`
- `apps/web/e2e/test_one_topic_session43_interview_mode.py`

## 已知边界

- Step 6 导出依赖后端 `18181`
- 后端不可用时，前端必须明确显示离线提示，不能假装导出成功
- Demo Case 是固定演示数据，不代表实时联网检索结果
- 多 Agent、LangGraph runtime、真实向量库仍不是当前默认执行链路

## 面试认知速查（繁简术语对照）

> 本项目文档以简体为主，下表列出面试官常问的九个认知点（繁体原文 + 简体对照）：

### 1. 專案定位

简体：项目定位

### 2. 目標用戶

简体：目标用户

### 3. 核心問題

简体：核心问题

### 4. 技術架構

简体：技术架构

### 5. 技術難點

简体：技术难点

### 6. 測試

简体：测试

### 7. 安全邊界

简体：安全边界

### 8. 演示路徑

简体：演示路径

### 9. 未來擴展

简体：未来发展
