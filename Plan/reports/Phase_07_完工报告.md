# Phase 07 完工报告：开题报告生成与委员会审查

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_07_开题报告生成与委员会审查.md`
> 日期：2026-06-16
> 状态：**149/149 pytest 通过（含 22 条 Phase 07 测试）**

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 06 给出 WorkPackagePlan 后，下一步必须**生成开题报告骨架 + 委员会审查**：

> 开题报告怎么写？10 节怎么填？
> 创新点怎么绑定问题/方法/实验？
> 委员会最常问的 6 个问题怎么准备？

合集反复强调"开题不是孤立文档，而是毕业论文骨架""开题报告要展现工作量、创新点、实验方案和风险预案"。Phase 07 把这条工程化为 4 个 Pydantic 对象 + 7 维度审查规则。

### 1.2 工程问题

ProposalDraft + CommitteeReview 是 Phase 08（最终材料导出）的输入。**Markdown 初稿**直接由 ProposalDraft.proposal_sections[i].content 拼出，**DOCX 导出**复用同一字段集。Phase 07 把字段锁死。

### 1.3 纯规则 vs LLM

- **10 节内容**纯规则模板：每节由 Phase 01-06 已有字段拼出
- **创新点**纯规则：从 WorkPackageFinal.innovation_binding 解析
- **研究现状**纯规则：按 method_family 分类，引用 ledger.papers 前 5
- **委员会 7 维度**纯规则 verdict（基于 issues 数量 + risk 评级）
- **6 个常见问题**固定模板

LLM 留给 Phase 08（章节文本润色）或后续扩展。

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase7_models.py`，108 行）

```python
class ProposalSection(BaseModel)        # key (10 SectionKey) / title / content / sources
class InnovationPoint(BaseModel)        # problem / method / verification / metrics / risk
class ResearchStatusRow(BaseModel)     # category / representative_work / gap / relation
class ProposalDraft(BaseModel)          # final_topic + 10 sections + innovation_points + research_status + timeline + risk_plan
class CommitteeReviewItem(BaseModel)    # dimension / verdict (4 选 1) / issues / suggestions
class CommitteeQuestion(BaseModel)     # question / suggested_answer / evidence_source
class CommitteeReview(BaseModel)        # 7 reviews + questions + checklist + overall_verdict + maturity
```

`PROPOSAL_SECTIONS` = 10 个固定 SectionKey 字面量。

### 2.2 节点（`packages/agents/nodes/phase7_proposal.py`，360 行）

**10 节 ProposalDraft 模板**：

| 节 | 来源 | 关键字段 |
|---|---|---|
| 1. 研究背景与意义 | ProjectIntake + TopicSpec | 题目 + goal_level 描述 |
| 2. 国内外研究现状 | EvidenceLedger.papers (前 5 by evidence_score) + surveys | 论文列表 |
| 3. 研究问题与目标 | WorkPackage.research_question | 2 个 WP 的 research_question |
| 4. 研究内容与技术路线 | WorkPackage.method_approach | 2 个 WP 的方法 |
| 5. 拟解决关键问题 | EvidenceLedger + Plan | 题目 + 数据/baseline 数量 |
| 6. 预期创新点 | WorkPackage.innovation_binding | 2 个 WP 的创新点描述 |
| 7. 实验方案与评价指标 | ExperimentMatrix + MetricSet | 主+补充实验 + 评价指标 |
| 8. 可行性分析 | ProjectIntake + EvidenceLedger | 数据/baseline/继承资源 |
| 9. 进度计划 | ProjectIntake 时间红线 | 5 阶段时间表 |
| 10. 风险预案 | RiskEvaluation + Plan.max_writing_risk | 最高风险维度 + pivot 候选 |

**7 维度 CommitteeReview 规则**：

| 维度 | 触发 issues 的条件 |
|---|---|
| 题目边界 | from_pivot=True / 题目含高风险词 |
| 研究现状 | papers < 5 / 无 surveys |
| 创新点 | 任何 WP 缺 innovation_binding |
| 数据与 baseline | datasets < 2 / baselines < 2 / 无 metrics |
| 实验方案 | 任何 WP 缺主/补充实验 |
| 工作量 | work_packages < 2 |
| 风险预案 | C/D 但无 pivot / max_writing_risk 含"高" |

**verdict 等级**（基于 issues 数量 + risk 评级）：

| conditions | verdict |
|---|---|
| issues = 0 | 通过 |
| issues ≤ 2 且 A/B | 有条件通过 |
| issues ≤ 4 | 需修改 |
| issues > 4 | 不通过 |

**6 个常见问题**（每条带 suggested_answer + evidence_source）：

1. 这个题目为什么值得做？
2. 现有方法有什么不足？
3. 你的创新点在哪里？
4. 你的数据和 baseline 从哪里来？
5. 实验怎么证明有效？
6. 做不出来怎么办？

**overall_verdict** = 7 reviews 中最严格的
**proposal_maturity** 跟 risk 评级松绑（A=A, B=B, C=C, D=C）
**allow_proceed_to_phase08** = overall ∈ (通过, 有条件通过) 且 rating ≠ D

### 2.3 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/proposal/draft` | 生成 10 节 ProposalDraft，落库 |
| GET | `/api/v1/projects/{id}/proposal/draft` | 取已落库 |
| POST | `/api/v1/projects/{id}/committee/review` | 生成 7 维度 CommitteeReview，落库 |
| GET | `/api/v1/projects/{id}/committee/review` | 取已落库 |

### 2.4 新表 `proposal_drafts` + `committee_reviews`

```python
class ProposalDraftRow(Base):
    id / project_id (unique) / case_id / payload (JSON) / final_topic (str)
class CommitteeReviewRow(Base):
    id / project_id (unique) / case_id / payload (JSON)
    / overall_verdict / proposal_maturity / allow_proceed_to_phase08 (bool)
```

仓储 `apps/api/app/db/proposal_repository.py`：两类仓储 + upsert。

### 2.5 测试（22 条）

- `test_phase7_models.py`（14 条）：PROPOSAL_SECTIONS 10 个、10 节齐全、content + sources 必填、创新点匹配 WP、研究现状分类、时间线、风险预案、7 维度、6 问题、verdict 有效、maturity 有效、allow_proceed、revision_checklist 格式、D 阻断
- `test_phase7_api.py`（8 条）：draft 端点、GET 持久化、committee 7 维度、GET 持久化、无 work_package 404、不存在 404、未生成 404、upsert 幂等

**149/149 pytest 全过**（原 127 + 新 22）。

---

## 3. 数据流：POST proposal/draft + committee/review 端到端

```text
WorkPackagePlan + RiskEvaluation + EvidenceLedger + TopicSpec + ProjectIntake (from DB)
                  │
                  ▼  (FastAPI 路由)
        各 repo 校验: 无 → 404/409
                  │
                  ▼  (Phase 07 入口)
        build_proposal_draft(intake, spec_topic, ledger, wp, risk_ev)
          ├─ 10 节 _section_* 拼装 (纯规则)
          ├─ _build_innovations(plan, ledger) → 2 个 InnovationPoint
          ├─ _build_research_status(ledger) → 分类行
          ├─ _build_timeline(intake) → 5 阶段
          └─ _build_risk_plan(risk_ev, plan) → 风险预案列表
                  │
                  ▼  (落库)
        ProposalDraftRepository.upsert(draft)
                  │
                  ▼  (响应)
        { section_count: 10, innovation_count: 2, payload: <ProposalDraft JSON> }


        build_committee_review(ledger, risk_ev, plan)
          ├─ _build_reviews → 7 维度 (题目边界/研究现状/创新点/...)
          ├─ _build_questions → 6 常见问题
          ├─ _build_revision_checklist → P0/P1 修改项
          └─ overall_verdict + proposal_maturity + allow_proceed
                  │
                  ▼  (落库)
        CommitteeReviewRepository.upsert(review)
                  │
                  ▼  (响应)
        { overall_verdict, proposal_maturity, review_count: 7, question_count: 6,
          allow_proceed_to_phase08, payload: <CommitteeReview JSON> }
```

---

## 4. 验收对照（Phase 07 §5）

| 条目 | 状态 |
|------|------|
| 开题报告骨架包含 10 个必要部分 | ✓ `test_proposal_draft_has_ten_sections` |
| 国内外研究现状按类别组织 | ✓ `_build_research_status` 按 method_family 分类 |
| 每个创新点绑定问题、方法和实验 | ✓ InnovationPoint 4 字段 + `innovation_binding` 链接 |
| 实验方案包含数据、baseline、指标和主实验 | ✓ §7 内容包含 ExperimentMatrix + MetricSet |
| 风险预案能回应 Phase 05 的最高风险项 | ✓ §10 = max_risk_dimension + decision |
| 委员会审查至少覆盖 7 个维度 | ✓ `test_committee_review_seven_dimensions` |
| 输出追问清单和修改清单 | ✓ `test_committee_questions_six` + `test_revision_checklist_format` |
| 不允许出现没有证据来源的强结论 | ✓ 每节 `sources` 必填 |

---

## 5. 与规约的偏离

无字段偏离。两条**实现细节**显式标注：

1. **不调 LLM**——文档 §2.1/§2.2 没强制要求 LLM，规则版 100% 可回归。LLM 留给 Phase 08 章节润色。
2. **7 维度 verdict 用规则评分**（issues 数量 + risk 评级）—— 不接 LangGraph 多 Agent 辩论（MVP 不引入 AutoGen / CrewAI）。

---

## 6. 与 Phase 08 的交接

- `ProposalDraft.proposal_sections[].content` → Markdown 初稿每节正文
- `ProposalDraft.proposal_sections[].title` → Markdown 标题
- `ProposalDraft.innovation_points` → Markdown 创新点表
- `ProposalDraft.research_status` → Markdown 国内外研究现状表
- `ProposalDraft.timeline` → Markdown 进度计划表
- `ProposalDraft.risk_plan` → Markdown 风险预案列表
- `CommitteeReview.overall_verdict` → 开题材料成熟度标签
- `CommitteeReview.questions` → 答辩前问答准备
- `CommitteeReview.revision_checklist` → 修改清单
- `allow_proceed_to_phase08=False` → 阻断 Phase 08

---

## 7. 不在本 Phase 的范围

- **LaTeX / Overleaf 模板**（Phase 08）
- **DOCX 导出**（Phase 08）
- **答辩 PPT 生成**（不在 8 Phase 范围内）
- **委员会多 Agent 辩论 / LangGraph 子图**（§3 文档设计但 MVP 不实现）
- **章节内容润色 LLM 调用**（Phase 08 升级时接入）

---

## 8. 一句话总结

> Phase 07 用纯规则把 WorkPackagePlan + RiskEvaluation + EvidenceLedger + TopicSpec 翻译为 10 节 ProposalDraft + 7 维度 CommitteeReview + 6 常见问题 + 自动修改清单。22 端到端测试守护 10 节齐全 + 7 维度齐全 + 6 问题齐全 + revision_checklist 格式 + D 评级阻断。149/149 pytest 全过。
