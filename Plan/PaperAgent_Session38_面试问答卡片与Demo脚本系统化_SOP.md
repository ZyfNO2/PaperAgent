# PaperAgent Session 38 SOP：面试问答卡片与 Demo 脚本系统化

> 日期：2026-06-21  
> 前置：S33 已有面试材料包，S34-S37 已补技术解释。  
> 本轮目标：把面试问答卡片和 Demo 脚本做成结构化、可检索、可演练的材料。

---

## 1. 面试解释

### 面试官可能会问

```text
你这个项目最大的技术难点是什么？
你怎么防幻觉？
RAG 怎么评估？
Agent 记忆怎么恢复？
如果我要你扩展成多 Agent 怎么做？
```

### 为什么需要这么改

用户资料里的大模型自学与面试方法强调：项目不仅要做出来，还要能被讲清。面试不是背功能列表，而是围绕项目被连续追问。结构化 QA 卡和 Demo 脚本能帮助面试时稳定输出。

---

## 2. 产物

```text
docs/interview/Interview_QA_Cards.md
docs/interview/Demo_Script_3min.md
docs/interview/Demo_Script_10min.md
docs/interview/Deep_Dive_QA_RAG.md
docs/interview/Deep_Dive_QA_Agent.md
docs/interview/Deep_Dive_QA_Memory.md
docs/interview/Deep_Dive_QA_MCP.md
```

---

## 3. QA 卡要求

至少 60 张：

```text
项目总览 10；
RAG 10；
Agent 10；
Memory 10；
MCP / Tool 8；
Testing / Eval 8；
Safety / Failure 4。
```

每张卡：

```text
question
short_answer
deep_answer
project_evidence
files_to_show
follow_up
weakness_or_boundary
```

---

## 4. Demo 脚本

3 分钟：

```text
只讲价值、流程、一个关键边界 Candidate != Evidence。
```

10 分钟：

```text
展示完整链路、Trace、失败案例、readiness、测试。
```

---

## 5. 测试

```text
1. QA Cards >= 60；
2. 每张卡包含 project_evidence；
3. Demo 3min <= 900 字；
4. Demo 10min 有步骤编号；
5. Deep Dive 文档覆盖 RAG/Agent/Memory/MCP；
6. 每个文档至少引用一个项目文件；
7. 包含“当前不足”；
8. 不出现夸大承诺。
```

---

## 6. 验收标准

```text
1. 面试 QA 可直接使用；
2. Demo 脚本和当前系统一致；
3. 每个回答都有项目证据；
4. 有边界和不足；
5. 完工报告包含“面试解释”。
```

---

## 7. 完工报告

```text
Plan/reports/Session_38_InterviewQA_DemoScripts_验收报告.md
```

