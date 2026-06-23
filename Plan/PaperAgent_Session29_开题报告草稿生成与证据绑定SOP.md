# PaperAgent Session 29 SOP：开题报告草稿生成与证据绑定

> 日期：2026-06-21  
> 前置：Session 28 已有可行性裁决。  
> 本轮目标：生成一份可审查的开题报告草稿，每个关键段落都能追溯到 EvidenceRef、SelectedResource 或明确的 missing evidence。

---

## 1. 目标

```text
生成开题报告草稿，但不冒充最终稿。
```

草稿用途：

```text
给学生和导师讨论；
暴露证据缺口；
明确工作量和创新点；
为后续 DOCX / 学校模板导出做结构准备。
```

---

## 2. 报告结构

```text
1. 题目与研究方向；
2. 研究背景与意义；
3. 国内外研究现状；
4. 研究目标；
5. 研究内容；
6. 技术路线；
7. 数据集与实验设计；
8. 预期创新点；
9. 工作量拆解；
10. 可行性与风险；
11. 参考资源清单；
12. 待补证据。
```

---

## 3. 证据绑定

每段必须包含：

```text
section_id
content
evidence_refs[]
selected_refs[]
candidate_refs[]
missing_evidence[]
confidence: high | medium | low
```

硬规则：

```text
没有 evidence_refs 的段落不能标 high；
只有 candidate_refs 的段落必须标 low 或 medium；
missing_evidence 必须显示给用户；
LLM 不得编造参考文献。
```

---

## 4. 工作量与创新点

工作量至少输出：

```text
1. 数据准备；
2. baseline 复现；
3. 方法改进；
4. 实验对比；
5. 消融实验；
6. 系统或可视化 Demo；
7. 论文写作与答辩材料。
```

创新点必须降温：

```text
不说“首创”；
优先说“面向某对象的轻量改进/工程化适配/实验对比补充”；
每个创新点都要说明证据基础和风险。
```

---

## 5. 测试

后端：

```text
1. 报告 12 节齐全；
2. 每节有 evidence_refs 或 missing_evidence；
3. 无证据段落 confidence 不得 high；
4. 工作量不少于 5 项；
5. 创新点不少于 2 项且无夸大词；
6. 参考资源来自 Candidate/Selected/Evidence；
7. 不编造 URL；
8. S28 裁决进入报告。
```

Playwright：

```text
S29-PW-1：报告草稿页可打开；
S29-PW-2：12 节可折叠浏览；
S29-PW-3：每节显示证据绑定；
S29-PW-4：缺证据警告可见；
S29-PW-5：工作量卡可见；
S29-PW-6：创新点卡可见；
S29-PW-7：无证据段落不会显示高置信；
S29-PW-8：S28 风险裁决可见。
```

---

## 6. 验收标准

```text
1. 开题报告草稿结构完整；
2. 关键段落有证据绑定；
3. 缺口明确显示；
4. 工作量和创新点可用于开题报告；
5. 不编造文献；
6. 后端测试通过；
7. Playwright 通过。
```

---

## 7. 完工报告

```text
Plan/reports/Session_29_ProposalDraft_EvidenceBound_验收报告.md
```

