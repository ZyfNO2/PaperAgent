# PaperAgent Session 12 SOP：报告质量检查与低门槛委员会复核

> 日期：2026-06-19  
> 阶段定位：在 Session 08 的 Markdown 导出、Session 10 的证据验证、Session 11 的 Trace 持久化基础上，对开题报告做结构化质量检查。  
> 本轮目标：检查报告是否“有证据、能开题、风险可解释、修改清单明确”，而不是做复杂多 Agent 严格审稿。

---

## 1. 当前状态判断

当前系统已经可以：

```text
生成开题报告 Markdown；
展示 EvidenceRef 引用；
显示 URL 验证状态；
记录用户如何选择和排除证据。
```

下一步需要回答：

```text
这份开题报告能不能给导师看？
哪些地方证据不足？
哪些创新点说得太满？
哪些工作包没有 dataset / baseline 支撑？
答辩会被问什么？
```

---

## 2. Session 12 目标

Session 12 名称：

```text
报告质量检查与低门槛委员会复核
```

目标：

```text
FinalPackage Markdown
+ EvidenceRef
+ Verification
+ Trace
→ QualityReview
→ 修改清单
→ 低门槛委员会 verdict
```

输出不是顶会审稿，而是开题场景的低门槛审核：

```text
通过 / 有条件通过 / 需修改 / 不建议
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做复杂多 Agent 辩论 | 先做规则 + 单轮 LLM/heuristic 复核 |
| 不模拟真实导师人格 | Professor_skill 思路后置 |
| 不做完整论文润色 | 只检查开题报告骨架质量 |
| 不要求严格学术新颖性证明 | 开题阶段低门槛 |
| 不生成长篇正文 | 只输出评审结果和修改清单 |

---

## 4. QualityReview 数据结构

建议新增：

```python
class ReportQualityCheck(BaseModel):
    dimension: str
    result: Literal["通过", "有条件通过", "需修改", "不建议"]
    score: float
    evidence_refs: list[EvidenceRef] = []
    issues: list[str] = []
    suggestions: list[str] = []

class ReportQualityReview(BaseModel):
    project_id: str
    verdict: Literal["通过", "有条件通过", "需修改", "不建议"]
    score: float
    checks: list[ReportQualityCheck]
    revision_checklist: list[str]
    defense_questions: list[DefenseQuestion]
    reviewed_at: str
```

答辩问题：

```python
class DefenseQuestion(BaseModel):
    question: str
    risk_level: Literal["低", "中", "高"]
    suggested_answer: str
    evidence_refs: list[EvidenceRef] = []
```

---

## 5. 审核维度

建议 8 维：

| 维度 | 检查内容 |
|---|---|
| 题目边界 | 是否过宽，是否有对象/任务/方法 |
| 研究现状 | 是否有 paper refs，是否有 verified/partial 来源 |
| 数据集 | 是否有 dataset ref，license/download 是否明确 |
| Baseline | 是否有 repo/baseline ref，是否可复现 |
| 工作包 | 每个 WP 是否有 paper/dataset/repo/metric 支撑 |
| 创新点 | 是否过度宣传，是否能用实验验证 |
| 风险预案 | 是否覆盖数据、baseline、时间、算力风险 |
| 表达清晰度 | 是否像开题报告而不是聊天总结 |

---

## 6. 评分规则

MVP 规则：

```text
每维 0-100；
≥80 通过；
60-79 有条件通过；
40-59 需修改；
<40 不建议。
```

总体 verdict：

```text
存在任一 “不建议” 关键维度 → 总体不建议；
存在 2 个以上 “需修改” → 总体需修改；
存在 1 个 “需修改” 或 2 个以上 “有条件通过” → 有条件通过；
否则通过。
```

关键维度：

```text
数据集；
Baseline；
工作包；
证据覆盖。
```

---

## 7. API 设计

### 7.1 构建报告审核

```text
POST /api/v1/one-topic/{project_id}/report/review
```

请求：

```json
{
  "mode": "light",
  "use_llm": false,
  "include_trace": true
}
```

响应：

```json
{
  "project_id": "ot_xxx",
  "verdict": "有条件通过",
  "score": 72,
  "checks": [],
  "revision_checklist": [],
  "defense_questions": []
}
```

### 7.2 获取最近审核

```text
GET /api/v1/one-topic/{project_id}/report/review
```

### 7.3 导出审核 Markdown

```text
GET /api/v1/one-topic/{project_id}/report/review/markdown
```

---

## 8. FinalPackage 联动

开题报告 Markdown 可追加：

```markdown
## 十五、低门槛审核结果

| 维度 | 结果 | 分数 | 问题 | 修改建议 |
|---|---|---:|---|---|

## 十六、开题答辩可能追问
```

或提供独立审核 Markdown。

MVP 推荐：

```text
先独立导出审核结果；
不强行改写原始开题报告。
```

---

## 9. 前端设计

新增区域：

```text
报告质量检查
├── 运行审核
├── verdict badge
├── 总分
├── 8 维检查表
├── 修改清单
└── 答辩追问
```

每条问题必须显示：

```text
关联 evidence refs；
关联章节；
建议修改动作。
```

---

## 10. 测试要求

### 10.1 后端测试

新增：

```text
apps/api/tests/test_session12_report_quality.py
```

覆盖：

```text
1. 能基于 FinalPackage 构建 QualityReview
2. 缺 dataset ref 时数据集维度需修改
3. 缺 baseline ref 时 baseline 维度需修改
4. rejected evidence 不得支撑通过
5. failed verification 降低分数
6. 每个 work_package 有支撑证据时工作包维度通过
7. 生成 revision_checklist
8. 生成 defense_questions
9. GET 最近 review 可用
10. review 不改变 evidence 状态
```

### 10.2 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session12_report_quality.py
```

覆盖：

```text
1. 页面出现报告质量检查区
2. 点击运行审核显示 verdict
3. 显示 8 维检查表
4. 显示修改清单
5. 显示答辩追问
6. evidence refs 在审核结果中可见
```

---

## 11. 验收标准

通过条件：

```text
1. 可对已有 FinalPackage 运行质量检查；
2. 输出总体 verdict 和总分；
3. 输出 8 维检查；
4. 输出修改清单；
5. 输出答辩追问；
6. 检查结果绑定 EvidenceRef；
7. failed/unverified 证据会影响评分；
8. 前端可展示审核结果；
9. 后端测试通过；
10. Playwright 测试通过。
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_12_ReportQuality_Review_验收报告.md
```

报告包含：

```text
范围；
审核模型；
评分规则；
新增 API；
前端变化；
测试结果；
未做项；
下一 Session 建议。
```

---

## 13. 下一 Session 预告

Session 13：内部 Skill Registry 最小版。

理由：

```text
现在已有 paper-card、dataset-validation、github-baseline、evidence-ledger 等内部 skill 文档，
但它们还没有注册、索引和统一 metadata。
```
