# PaperAgent Session 40 SOP：简历项目包装与技术亮点收束

> 日期：2026-06-21  
> 前置：S33-S39 已有技术解释、QA、Demo、失败案例。  
> 本轮目标：把 PaperAgent 收束为可放简历、可投递、可面试展示的项目材料。

---

## 1. 面试解释

### 面试官可能会问

```text
你在项目里具体负责什么？
项目难点是什么？
你做了哪些工程化保障？
相比普通 RAG 项目有什么区别？
如果继续迭代你会怎么做？
```

### 为什么需要这么改

你给的自学与面试资料强调：项目要能挂简历，且要能从“做了什么”升级成“解决了什么问题、怎么评估、怎么保证可靠”。S40 的目标就是把前面所有技术点压缩成简历、面试、自我介绍三种表达。

---

## 2. 产物

```text
docs/interview/Resume_Bullets.md
docs/interview/Self_Introduction_1min.md
docs/interview/Self_Introduction_3min.md
docs/interview/Project_DeepDive_Index.md
docs/interview/Technical_Highlights.md
docs/interview/Known_Limitations_For_Interview.md
```

---

## 3. 简历 bullets

至少 8 条，分三档：

```text
短版：适合一页简历；
中版：适合项目经历；
长版：适合面试展开。
```

必须覆盖：

```text
RAG；
Agent workflow；
Evidence governance；
Memory / replay；
MCP / tool boundary；
Evaluation / Playwright；
Readiness / compliance；
Failure handling。
```

---

## 4. 技术亮点收束

建议最终 5 个亮点：

```text
1. 多阶段科研证据 Agent Workflow；
2. Candidate -> Evidence 的证据治理闸门；
3. RunEvent / Trace / Baseline 的可回放工程闭环；
4. 面试级 RAG Pipeline 与评估设计；
5. 导出前 Readiness 与失败案例硬拦截。
```

---

## 5. 测试

```text
1. Resume_Bullets 至少 8 条；
2. 1min 自我介绍 <= 500 字；
3. 3min 自我介绍包含项目背景、架构、难点、测试；
4. Technical_Highlights 至少 5 项；
5. Known_Limitations 明确不夸大；
6. 每个亮点能链接到项目文件或测试；
7. 不出现“保证通过开题”“完全避免幻觉”等绝对承诺。
```

---

## 6. 验收标准

```text
1. 简历材料可直接使用；
2. 自我介绍可直接背诵；
3. 技术亮点对应真实实现；
4. 已知限制诚实；
5. 可支撑一次 30 分钟项目深挖；
6. 完工报告包含“面试解释”。
```

---

## 7. 完工报告

```text
Plan/reports/Session_40_ResumePackaging_TechHighlights_验收报告.md
```

