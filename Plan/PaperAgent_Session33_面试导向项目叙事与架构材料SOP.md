# PaperAgent Session 33 SOP：面试导向项目叙事与架构材料

> 日期：2026-06-21  
> 前置：S25-S32 已完成工作台、证据晋升、可行性、报告草稿、委员会复核、全链路 baseline、导出前检查。  
> 本轮目标：不新增大功能，先把项目整理成“面试可讲、可演示、可被深挖”的材料包。

---

## 1. 本轮目标

```text
把 PaperAgent 包装为一个面向大模型应用/Agent/RAG 岗位的项目作品。
```

具体目标：

```text
1. 写项目 OnePager；
2. 写面试架构图；
3. 写 RAG/Agent/Memory/Tool/Eval 五类问答卡；
4. 写 3 分钟项目介绍稿；
5. 写 10 分钟 Demo 脚本；
6. 整理失败案例和已知边界；
7. 记录当前测试与未修复风险。
```

---

## 2. 本轮不做什么

```text
不新增复杂检索；
不重构后端；
不做 MCP Server；
不新增多 Agent；
不修所有历史技术债；
不改 Evidence 规则。
```

本轮是面试材料整理，不是功能冲刺。

---

## 3. 新增文档

```text
docs/interview/Project_OnePager.md
docs/interview/Architecture_Diagram.md
docs/interview/Interview_QA_Cards.md
docs/interview/Demo_Script_3min.md
docs/interview/Demo_Script_10min.md
docs/interview/Failure_Cases.md
docs/interview/Resume_Bullets.md
```

如果 `docs/interview/` 不存在则新建。

---

## 4. Project OnePager

必须包含：

```text
项目定位；
目标用户；
核心问题；
核心流程；
技术架构；
技术难点；
测试与评估；
安全边界；
演示路径；
未来扩展。
```

一句话定位：

```text
PaperAgent 是一个面向毕业论文开题的科研证据 Agent 工作台，通过多阶段 RAG、证据晋升、流式可回放和导出前合规检查，帮助学生把题目变成可验证的开题方案。
```

---

## 5. Architecture Diagram

必须画两张：

```text
1. 用户流程图；
2. 技术架构图。
```

技术架构图必须包含：

```text
Frontend Step Deck；
PromptProtocol；
ComponentRegistry；
CandidateResource；
SelectedResource；
URLVerified；
EvidencePromotion；
EvidenceRef；
Feasibility；
ProposalDraft；
CommitteeReview；
Readiness；
Trace / RunEvent / Baseline。
```

---

## 6. Interview QA Cards

至少 30 张卡，分 6 类：

```text
RAG 类：5 张；
Agent 类：5 张；
Memory / Transcript 类：5 张；
Tool Calling / MCP 类：5 张；
Evaluation / Testing 类：5 张；
Safety / Boundary 类：5 张。
```

每张卡结构：

```text
问题；
面试官想考什么；
PaperAgent 怎么回答；
项目证据；
可展示文件；
风险补充。
```

示例问题：

```text
你的 RAG 为什么不是简单向量库？
你如何避免 LLM 幻觉？
你的 Agent 记忆怎么设计？
Function Calling 失败怎么办？
为什么不用复杂 Multi-Agent？
如何评估一个 Agent 项目？
候选资源为什么不能直接写进报告？
```

---

## 7. Demo Scripts

3 分钟脚本：

```text
输入题目；
关键词 Gate；
候选资源；
证据晋升；
可行性；
报告草稿；
readiness。
```

10 分钟脚本：

```text
再展示 Trace；
失败案例；
Candidate != Evidence；
高风险题目 PIVOT；
Playwright / baseline；
架构图。
```

---

## 8. Failure Cases

至少 6 类：

```text
无公开数据集；
无 baseline；
URL 未验证；
候选很多但无法复现；
创新点夸大；
导出前合规失败。
```

每类包含：

```text
输入；
系统如何拦截；
用户看到什么；
面试怎么解释；
对应测试。
```

---

## 9. 测试要求

本轮主要测试文档存在性和内容完整性。

后端可选：

```text
apps/api/tests/test_session33_interview_docs.py
```

断言：

```text
1. docs/interview 目录存在；
2. 7 个文档存在；
3. OnePager 包含 RAG / Agent / Evidence / Evaluation；
4. QA Cards 至少 30 个问题；
5. Demo Script 包含 3min / 10min；
6. Failure Cases 至少 6 类；
7. Resume Bullets 至少 5 条；
8. 明确记录 test_session6_llm_path.py 既有失败或已修复状态。
```

Playwright 可选：

```text
如果已有 docs 页面，可加一条“面试材料入口可打开”；
否则本轮不强制 Playwright。
```

---

## 10. 验收标准

```text
1. 面试材料包完整；
2. 架构图能对应当前实现；
3. QA 卡覆盖 RAG/Agent/Memory/MCP/Eval/Safety；
4. Demo 脚本能按当前系统跑；
5. 失败案例不粉饰风险；
6. 简历 bullets 能直接使用；
7. S31/S32 报告中的未修复风险被记录；
8. 不引入功能回归。
```

---

## 11. 完工报告

完成后新增：

```text
Plan/reports/Session_33_InterviewStoryPack_验收报告.md
```

报告必须写：

```text
1. 新增文档清单；
2. 30 张 QA 卡覆盖范围；
3. Demo 脚本；
4. 失败案例；
5. 简历描述；
6. 是否修复或记录 S31 的既有失败；
7. 后续是否进入 S34 RAG 面试级检索评估。
```

