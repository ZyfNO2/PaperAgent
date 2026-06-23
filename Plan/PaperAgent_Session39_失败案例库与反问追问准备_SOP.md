# PaperAgent Session 39 SOP：失败案例库与反问追问准备

> 日期：2026-06-21  
> 前置：S38 已有 QA 和 Demo。  
> 本轮目标：把失败案例整理成面试亮点，证明项目有边界意识、测试意识和工程判断。

---

## 1. 面试解释

### 面试官可能会问

```text
你的项目什么时候会失败？
失败了怎么恢复？
你怎么知道模型没胡说？
有哪些 case 是你主动拦截的？
你项目最大的不足是什么？
```

### 为什么需要这么改

真实面试很喜欢追问失败和边界。你的本地资料也反复强调“什么让 AI 做，什么不让 AI 做”。PaperAgent 已经有 Candidate != Evidence、Readiness hard block、高风险 Case 等材料，应该主动变成失败案例库。

---

## 2. 失败案例类型

至少 10 类：

```text
无公开数据集；
无 baseline；
URL 全部未验证；
候选很多但不能复现；
创新点夸大；
报告缺技术路线；
参考资源为空；
LLM 输出坏 JSON；
工具调用越权；
多 Agent 路由错误；
检索结果为空；
S31 中既有 test_session6_llm_path.py 失败。
```

---

## 3. 每个案例结构

```text
case_id
input
failure_trigger
system_block
user_visible_message
technical_reason
interview_explanation
related_tests
improvement_plan
```

---

## 4. 反问准备

准备 8 个反问：

```text
贵团队更关注 RAG 的召回质量还是证据可信度？
Agent 项目里你们更看重功能完成还是可观测性？
工具调用越权你们通常怎么做审计？
多 Agent 编排中你们怎么控制成本？
你们现在有没有 MCP 或内部工具生态？
科研/文档类 Agent 的评估指标通常怎么定？
面试官更希望我展示系统架构还是某个模块深挖？
如果继续做这个项目，你们建议优先补 RAG 还是 Memory？
```

---

## 5. 测试

```text
1. Failure_Cases >= 10；
2. 每个 case 有 system_block；
3. 每个 case 有 related_tests；
4. 包含一个真实历史失败；
5. 包含至少 8 个反问；
6. 不把失败写成缺点逃避，要写成工程边界。
```

---

## 6. 验收标准

```text
1. 失败案例库完整；
2. 失败能映射到测试；
3. 反问准备可用于面试；
4. 风险表达诚实；
5. 完工报告包含“面试解释”。
```

---

## 7. 完工报告

```text
Plan/reports/Session_39_FailureCases_InterviewFollowups_验收报告.md
```

