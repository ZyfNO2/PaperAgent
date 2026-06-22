# Demo Script 3 分钟

> 场景：`Interview Mode`
> 题目：`基于YOLO的钢材表面缺陷检测`

## 0. 入口（20 秒）

- 打开 `http://127.0.0.1:18182/?mode=interview`
- 点击“面试演示模式（加载 Demo Case）”

要点：

- 这是同一套工作台，不是单独的演示页面
- Demo Case 是固定演示数据，用于稳定讲述

## 1. Step Workbench（45 秒）

先看中间主工作台：

- Step 1：题目理解
- Step 2：关键词拆解
- Step 3：候选证据
- Step 4：可行性
- Step 5：开题建议

要点：

- 我不是一次性生成整份报告
- 每一步都可确认、可重跑、可回看

## 2. Trace / Memory（35 秒）

切到右栏 `证据 Trace`。

要点：

- 用户确认会写进 Trace
- 修改记录会保留
- 后续被影响的步骤会变成 `stale`

## 3. 对话式修改（40 秒）

切到左栏 `LLM 思维 / 对话`。

演示口径：

- `仅讨论` 不会改状态
- `生成修改建议` 会先出预览卡
- 用户确认后才真正写入

核心句：

> 我把聊天入口做成了可审计工作台操作，而不是让 LLM 直接改数据。

## 4. 导出前检查（30 秒）

看 Step 6 导出区。

要点：

- 只有 Step 1-5 完成且没有 `stale` 才允许导出
- 如果后端 `18181` 离线，前端会明确提示，不会伪装导出成功

## 收尾（10 秒）

> PaperAgent 把“能不能开题”做成了一个可追溯、可修改、可讲解的 Agent 工作台；面试模式只是把这套真实工作流变成了可稳定展示的入口。


##涉及文件

- `apps/web/e2e/test_one_topic_session43_interview_mode.py`
- `apps/web/step_workbench.js`
- `docs/interview/Project_OnePager.md`
