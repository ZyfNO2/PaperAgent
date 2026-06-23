# PaperAgent Session 23 SOP：流式 Prompt 协议与工具调用边界

> 日期：2026-06-20  
> 前置：Session 22 应完成 Renderer Component Registry。  
> 本轮目标：定义 LLM 如何一边输出自然语言，一边输出受控 `paperagent-card` / `card_delta`，并明确哪些步骤必须等待用户 Gate 后才能调用检索或写入候选资源。

---

## 1. 本轮目标

```text
把 LLM 输出从“随意 Markdown”约束为：
自然语言解释 + 结构化 render block + 固定事件流
```

本轮产物：

```text
1. 流式 Prompt 协议；
2. 每个 Step 的输出合同；
3. token_delta / card_delta 切换规则；
4. 工具调用前置 Gate；
5. prompt 安全条款；
6. 失败降级策略。
```

---

## 2. 不做什么

```text
不接多个模型；
不做复杂 Agent 编排；
不做真实大规模联网检索；
不让 LLM 直接写 Evidence Ledger；
不让 LLM 绕过 keyword_review；
不允许 LLM 输出 script / style / iframe / onClick。
```

---

## 3. 输出协议

LLM 允许输出两类内容：

```text
1. 普通文本：用于 token_delta；
2. 结构化卡片：用于 paperagent-card 或 card_delta。
```

普通文本示例：

```text
我正在识别题目中的方法、任务和研究对象。这个题目包含一个典型的计算机视觉检测任务。
```

结构化卡片示例：

````text
```paperagent-card
{
  "component": "KeywordReviewCard",
  "props": {
    "keywords": [
      {"kind": "method", "text": "YOLO"},
      {"kind": "task", "text": "目标检测"},
      {"kind": "object", "text": "钢材表面缺陷"}
    ],
    "editable": true
  },
  "actions": [
    {"id": "approve", "event": "approve_step"},
    {"id": "revise", "event": "revise_step"}
  ]
}
```
````

---

## 4. Step 输出合同

### Step 1：topic_understanding

必须输出：

```text
1. 题目原文；
2. 任务理解；
3. 方法识别；
4. 研究对象识别；
5. 初步风险。
```

推荐组件：

```text
TopicUnderstandingCard
```

### Step 2：keyword_review

必须输出：

```text
1. method keywords；
2. task keywords；
3. object keywords；
4. domain keywords；
5. risk / constraint keywords；
6. step_pause。
```

推荐组件：

```text
KeywordReviewCard
```

硬规则：

```text
keyword_review 后必须暂停；
用户未确认前不能进入真实检索。
```

### Step 3：query_plan

必须输出：

```text
1. paper queries；
2. dataset queries；
3. repo queries；
4. 中文 query；
5. 英文 query；
6. 每条 query 对应的关键词来源。
```

推荐组件：

```text
SearchQueryPlanCard
```

### Step 4：candidate_resources

必须输出：

```text
1. candidate，不是 evidence；
2. 来源 URL；
3. 匹配关键词；
4. 初步推荐理由；
5. 风险标签；
6. 用户动作：保存、淘汰、需要复核。
```

推荐组件：

```text
RetrievalCandidateCard
```

---

## 5. 事件流规则

推荐事件顺序：

```text
run_started
step_started(topic_understanding)
token_delta...
card_delta(TopicUnderstandingCard)
step_completed(topic_understanding)
step_started(keyword_review)
token_delta...
card_delta(KeywordReviewCard)
step_pause(keyword_review)
user_patch_required(keyword_review)
step_resumed
step_started(query_plan)
card_delta(SearchQueryPlanCard)
```

注意：

```text
如果真实后端暂未落地，可以先用前端 mock 对齐事件顺序；
但 prompt 文档必须按真实事件设计，避免后续返工。
```

---

## 6. 工具调用边界

允许调用前：

```text
1. keyword_review 已 approved；
2. query_plan 已生成；
3. 用户没有标记“重新拆解关键词”；
4. 当前 run 没有 failed；
5. action 来源是注册表 action，不是 LLM 自造指令。
```

禁止：

```text
LLM 直接调用外部检索；
LLM 直接写入 Evidence Ledger；
LLM 直接把 candidate 标为 verified；
LLM 直接生成 supports；
LLM 跳过 URLVerified。
```

---

## 7. Prompt 安全条款

每个 prompt 必须包含：

```text
你只能输出普通文本和 paperagent-card JSON；
不得输出 HTML；
不得输出 script/style/iframe/object/embed；
不得输出 onClick/onerror/onload 等事件处理器；
不得输出 eval/new Function/javascript:；
不得要求前端执行任意代码；
不得把候选资源描述为已验证证据；
不得编造论文、数据集、GitHub 地址。
```

---

## 8. 失败降级

LLM 输出坏 JSON：

```text
显示普通文本；
渲染 invalid card；
保留原始输出片段；
提示用户可重试或切换 heuristic。
```

LLM 没有输出关键词卡：

```text
使用 heuristic 关键词拆解；
标记 fallback；
仍然进入 keyword_review Gate；
不得直接检索。
```

LLM 输出疑似脚本：

```text
安全降级；
写入安全事件；
不中断页面；
不执行内容。
```

---

## 9. 测试要求

后端或前端协议测试：

```text
S23-T-1：prompt skeleton 存在；
S23-T-2：KeywordReviewCard 示例能被 registry 解析；
S23-T-3：坏 JSON 降级；
S23-T-4：script payload 降级；
S23-T-5：未 approved keyword gate 不能进入 retrieval；
S23-T-6：approved 后允许生成 query_plan；
S23-T-7：candidate 不会被标为 evidence；
S23-T-8：S21/S22 Playwright 不回退。
```

---

## 10. 验收标准

```text
1. 有完整 Prompt 协议文档或代码内 prompt skeleton；
2. Step 1-4 输出合同明确；
3. token_delta / card_delta 规则明确；
4. keyword_review Gate 仍强制存在；
5. 工具调用边界明确；
6. 安全条款落地；
7. 失败降级可测；
8. 不破坏 S17 baseline。
```

---

## 11. 完工报告

完成后新增：

```text
Plan/reports/Session_23_StreamingPrompt_ToolBoundary_验收报告.md
```

报告必须写：

```text
1. Prompt 协议；
2. Step 输出合同；
3. 工具调用边界；
4. Gate 是否仍生效；
5. 安全条款；
6. 降级测试；
7. Playwright / 后端测试结果；
8. 对 Session 24 的输入合同。
```

