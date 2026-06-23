# PaperAgent Session 30 SOP：低门槛委员会复核与 Revision Loop

> 日期：2026-06-21  
> 前置：Session 29 已有开题报告草稿。  
> 本轮目标：对草稿做低门槛委员会复核，指出明显问题，并把修改建议回写为可执行任务。

---

## 1. 目标

```text
模拟“很宽松但认真”的开题前初审：
不是替代专家，而是帮用户发现明显不适合开题的问题。
```

---

## 2. 复核角色

```text
导师视角：题目是否可控；
方法视角：技术路线是否说得通；
实验视角：数据、baseline、指标是否齐；
写作视角：报告结构是否像开题报告；
风险视角：是否存在毕业风险。
```

---

## 3. 复核输出

```text
ReviewRound
  verdict: pass | conditional_pass | revise | reject
  issues[]
  required_actions[]
  optional_actions[]
  evidence_gaps[]
  next_revision_prompt
```

Issue：

```text
severity: fatal | high | medium | low
section_id
message
suggested_fix
evidence_refs[]
```

---

## 4. Revision Loop

用户可执行：

```text
accept_fix
ignore_issue
add_evidence
revise_keywords
revise_topic
regenerate_section
rerun_review
```

限制：

```text
ignore fatal issue 后不能标 pass；
add_evidence 必须回到 Candidate/Evidence 流程；
revise_topic 必须回到 keyword_review；
regenerate_section 不得编造证据。
```

---

## 5. 测试

后端：

```text
1. 缺数据集 -> 至少 high issue；
2. 无 baseline -> 至少 high issue；
3. 无证据段落 -> medium/high issue；
4. fatal issue 未处理不得 pass；
5. accept_fix 生成 revision action；
6. rerun_review 保留历史轮次；
7. revise_topic 触发回到 keyword_review；
8. ReviewRound 可序列化。
```

Playwright：

```text
S30-PW-1：委员会复核卡可见；
S30-PW-2：5 类视角意见可见；
S30-PW-3：问题按 severity 显示；
S30-PW-4：accept_fix 生成任务；
S30-PW-5：fatal 未处理不能通过；
S30-PW-6：rerun_review 增加轮次；
S30-PW-7：revise_topic 回到关键词页；
S30-PW-8：S29 报告草稿不回退。
```

---

## 6. 验收标准

```text
1. ReviewRound 结构化；
2. 至少 5 个复核视角；
3. 问题能转成 revision action；
4. fatal issue 有硬拦截；
5. 可重新复核；
6. 不编造证据；
7. 后端测试通过；
8. Playwright 通过。
```

---

## 7. 完工报告

```text
Plan/reports/Session_30_CommitteeReview_RevisionLoop_验收报告.md
```

