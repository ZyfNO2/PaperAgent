# PaperAgent Session 07 SOP：EvidenceRef 强制挂接与证据复核闭环

> 日期：2026-06-18  
> 短期目标对齐：继续围绕 `PaperAgent_交互式证据工作台改造计划书与SOP.md`，不偏离“证据工作台 + Human Gate + 可复核开题判断”主线。  
> 依据文档：
> - `Plan/Faraway/PaperAgent_交互式证据工作台改造计划书与SOP.md`
> - `Plan/Faraway/参考项目调研.md`
> - `Plan/Faraway/8Phase详解.md`
> - `Plan/Faraway/Agent化路线.md`
> - `Plan/Faraway/PaperAgent_科研Skill下载链接汇总.md`
> - `Plan/reports/Session_05_Evidence_Scoring_验收报告.md`
> - `Plan/reports/Session_06_LLM_Path_Activation_验收报告.md`

---

## 1. 新报告审阅结论

### 1.1 Session 05 审阅结论

Session 05 基本符合上一轮 SOP：

- 已完成论文、数据集、GitHub 工程三类证据评分；
- 已完成去重、分类、score summary、rescore API；
- 已完成证据工作台分数展示、排序、重新评分；
- 已新增 4 个内部科研 Skill 文档；
- 已将可行性判断从“看数量”升级为“看质量”。

可以视为 **通过验收**。

但有一个短期遗留点必须进入 Session 07：

```text
评分结果已经存在，但后续结论还没有强制绑定 evidence_id。
```

也就是说，系统现在能说“这个方向可做 / 可转向”，但还没有强制说明：

```text
这个判断具体由哪几篇论文、哪个数据集、哪个 repo 支撑。
```

---

### 1.2 Session 06 审阅结论

Session 06 做了 LLM 路径激活：

- LLM 搜索助手辅助关键词拆分；
- LLM rerank 过滤无关 arXiv；
- LLM 生成推荐题目、工作包和轻审核；
- 后端测试报告显示 60 tests pass + 1 skip；
- PINN 诊断中的无关论文、baseline 兜底等问题已被纳入修复。

但 Session 06 报告里有一个验收风险：

```text
前端 e2e 部分写的是“7 测试写完, subagent 跑中”，
后文又写“前端 7 e2e 验证”。
```

因此 Session 06 建议判定为：

```text
功能方向通过，正式验收需要补充前端 e2e 最终结果。
```

Session 07 开始前，应先要求补充或修订：

```text
Plan/reports/Session_06_LLM_Path_Activation_验收报告.md
```

至少明确：

- `apps/web/e2e/test_one_topic_session6_llm.py` 是否全部通过；
- 是否存在 LLM flake；
- 如果 flake，是否有 mock / fallback 测试覆盖；
- Playwright 是否覆盖真实页面上的推荐、审核、评分展示。

---

## 2. 下一 Session 设计原则

Session 07 不做远期扩张。

本阶段不要做：

| 不做 | 原因 |
|---|---|
| 不批量下载科研 Skill | 当前短期目标是证据工作台，不是 Skill Marketplace |
| 不做 PDF 全文 RAG | 会引入 Docling/GROBID 依赖，偏离当前 MVP |
| 不做完整 Phase 07 委员会多 Agent | 高质量证据链尚未绑定，先不升级评审复杂度 |
| 不做 DOCX / PPT 导出 | 当前还没到材料排版阶段 |
| 不做 Research Wiki 全量持久化 | 可作为后续方向，短期先做项目内 Trace |
| 不做 MCTS / LangGraph 大改 | 当前需要补证据约束，不是重写流程 |

本阶段只做一件事：

> 让每个关键结论都必须引用证据工作台中的 evidence_id，并允许用户在界面上复核这些引用。

---

## 3. 参考工程落地取舍

本次只吸收参考项目中和短期目标直接相关的设计。

| 参考项目 | 可借鉴点 | Session 07 落地方式 |
|---|---|---|
| idea-evaluation-pipeline | 每个判断后面都有 review，文献必须有 URL 校验 | 增加 `url_verified` / `ref_status`，未验证证据不得支撑核心结论 |
| ARIS | query_pack 硬预算、失败想法不剪枝 | 增加 `evidence_pack` 摘要，保留 rejected / pivot history |
| ResearchRubrics | verdict + confidence + evidence | 给结论绑定 `confidence` 与 `evidence_refs` |
| Professor_skill | 每条判断附证据链 | 可行性、Pivot、工作包、轻审核都附 evidence_id |
| AutoResearchClaw | HITL gate 和状态迁移 | 用户复核 EvidenceRef 后才能进入后续报告生成 |
| Claude Scholar | question → evidence → experiment → claim | 工作包结构变为“问题-证据-实验-结论” |

不落地：

- IRIS 的 MCTS；
- Idea2Proposal 的多 Agent ensemble；
- PaperQA2 / RAG_Gap_Finder 的全文 chunk；
- Skill Marketplace 同步器。

---

## 4. Session 07 目标

Session 07 名称：

```text
EvidenceRef 强制挂接与证据复核闭环
```

目标：

```text
Evidence Ledger
→ EvidenceRef 绑定
→ 结论可追溯
→ 用户可复核引用
→ Trace 记录复核动作
→ 后续开题报告只使用已绑定证据的结论
```

完成后，系统应从：

```text
有证据池 + 有评分 + LLM 会生成建议
```

升级为：

```text
每条可行性判断、Pivot 路线、工作包和审核意见都能追溯到具体证据。
```

---

## 5. 功能范围

### 5.1 新增 EvidenceRef 数据结构

建议新增统一引用结构：

```python
class EvidenceRef(BaseModel):
    evidence_id: str
    evidence_type: Literal["paper", "dataset", "repo", "baseline", "note"]
    title: str
    role: Literal[
        "supports",
        "warns",
        "blocks",
        "background",
        "alternative"
    ]
    reason: str
    score: float | None = None
    review_status: str
    url: str | None = None
    url_verified: bool | None = None
```

字段解释：

| 字段 | 作用 |
|---|---|
| `evidence_id` | 指向证据工作台中的真实证据 |
| `role` | 说明该证据是在支撑、警告、阻断还是背景引用 |
| `reason` | 用一句话说明为什么引用这条证据 |
| `score` | 复用 Session 05 的相关性或质量分 |
| `review_status` | 必须暴露用户审核状态 |
| `url_verified` | 是否有可访问 URL 或可验证来源 |

---

### 5.2 给 FeasibilitySummary 挂 evidence_refs

当前 `FeasibilitySummary` 只有：

```text
verdict
reason
paper_status
dataset_status
baseline_status
engineering_status
missing_evidence
recommended_next_action
```

Session 07 增加：

```python
evidence_refs: list[EvidenceRef] = []
blocking_refs: list[EvidenceRef] = []
missing_ref_reasons: list[str] = []
confidence: float
```

规则：

```text
可做:
  至少 2 篇 paper + 1 个 dataset + 1 个 repo/baseline evidence_ref

收缩后可做:
  至少有 paper 支撑，但 dataset/repo 有弱项或 warning refs

可转向:
  必须说明原题为什么风险高，以及转向路线引用哪些替代证据

暂缓:
  必须列出缺失证据原因，不允许只写笼统“材料不足”

不建议:
  必须有 blocking_refs 或明确 missing_ref_reasons
```

验收重点：

```text
没有 evidence_refs 的 feasibility 不允许进入报告生成。
```

---

### 5.3 给 PivotRoute 挂 evidence_refs

当前三条路线已有：

```text
conservative
balanced
aggressive
```

Session 07 每条路线增加：

```python
evidence_refs: list[EvidenceRef]
risk_reduction_refs: list[EvidenceRef]
missing_evidence: list[str]
confidence: float
```

每条路线必须回答：

```text
为什么这条路线更稳？
它保留了哪些证据？
它删除了哪些高风险部分？
它依赖哪个数据集？
它依赖哪个 baseline / repo？
它还有什么证据缺口？
```

前端展示：

```text
保守路线
├── 支撑证据：paper_001, dataset_002, repo_003
├── 风险降低依据：去掉多模态 / 去掉自采数据
├── 缺口：license 未确认
└── 置信度：0.72
```

---

### 5.4 给 WorkPackageSuggestion 挂 evidence_refs

当前工作包字段：

```text
wp_id
title
research_question
method_approach
data_source
experiment_plan
chapter
```

Session 07 增加：

```python
evidence_refs: list[EvidenceRef]
dataset_refs: list[EvidenceRef]
baseline_refs: list[EvidenceRef]
metric_refs: list[EvidenceRef]
open_questions: list[str]
```

工作包最低要求：

```text
每个 WP 至少绑定：
1 个 paper ref
1 个 dataset ref 或明确说明数据缺口
1 个 baseline/repo ref 或明确说明复现缺口
1 个 metric 来源或默认指标说明
```

如果无法满足，工作包必须降级：

```text
status = "needs_evidence"
```

不能继续伪装成可执行工作包。

---

### 5.5 给 ProposalRecommendation 挂 evidence_refs

推荐题目和推荐理由必须绑定证据：

```python
topic_evidence_refs: list[EvidenceRef]
reason_evidence_refs: dict[str, list[EvidenceRef]]
```

规则：

```text
每条 recommendation_reason 至少绑定 1 条 evidence_ref；
LLM 生成的理由如果找不到证据支撑，必须标记为 “待人工确认”；
开题报告草稿暂不引用未确认理由。
```

---

### 5.6 给 LightReview 挂 evidence_refs

轻审核每一维增加：

```python
evidence_refs: list[EvidenceRef]
confidence: float
```

示例：

```text
数据集与 Baseline：有条件通过
依据：
- dataset_002: NEU-DET，有公开下载，但 license 不清楚
- repo_003: YOLOv8 官方框架，可复现性较高
建议：
- 补充数据集 license 说明
```

---

## 6. EvidenceRef 选择规则

### 6.1 可引用证据

默认可引用：

```text
review_status in ["accepted", "core", "background"]
```

优先级：

```text
core > accepted > background > pending
```

默认不可引用：

```text
rejected
needs_check
```

例外：

```text
needs_check 可以作为 warns / blocks，但不能作为 supports。
rejected 可以作为 “反例/排除记录”，但不能支撑可做结论。
```

---

### 6.2 证据选择分数

建议内部使用：

```text
ref_priority =
  0.40 × review_weight
+ 0.30 × evidence_score
+ 0.15 × type_weight
+ 0.10 × recency_or_activity
+ 0.05 × url_verified
```

review_weight：

```text
core = 1.00
accepted = 0.80
background = 0.50
pending = 0.20
needs_check = 0.10
rejected = 0.00
```

type_weight：

```text
paper:
  survey / baseline_method / application > case_study > unknown > irrelevant

dataset:
  ready > needs_preprocess > needs_permission > weak_match > unverified > invalid

repo:
  official / baseline_framework > reproduction > demo_only > unknown > not_reproducible
```

---

## 7. API 设计

### 7.1 EvidenceRef 重建

```text
POST /api/v1/one-topic/{project_id}/evidence/refs/rebuild
```

用途：

```text
根据当前 evidence pool、review_status、score，重新给 feasibility / pivot / work_packages / review 绑定证据。
```

要求：

```text
不改变用户 review_status；
不删除证据；
只更新结论层的 evidence_refs；
返回 ref coverage summary。
```

---

### 7.2 EvidenceRef 覆盖率摘要

```text
GET /api/v1/one-topic/{project_id}/evidence/refs/coverage
```

输出：

```json
{
  "project_id": "ot_xxx",
  "feasibility_has_refs": true,
  "pivot_routes_with_refs": 3,
  "work_packages_with_refs": 2,
  "review_checks_with_refs": 5,
  "unsupported_claims": [
    "推荐理由 2 缺少 dataset evidence",
    "WP2 缺少 baseline repo"
  ],
  "coverage_score": 0.82
}
```

---

### 7.3 用户复核 EvidenceRef

```text
PATCH /api/v1/one-topic/{project_id}/evidence/refs/review
```

请求：

```json
{
  "target_type": "work_package",
  "target_id": "WP1",
  "evidence_id": "repo_003",
  "action": "remove_ref",
  "reason": "该 repo 只是 demo，不适合作为 baseline"
}
```

动作：

```text
add_ref
remove_ref
mark_ref_core
mark_ref_wrong
replace_ref
```

所有动作必须写入 Trace。

---

## 8. 前端工作台改造

### 8.1 证据引用面板

在当前证据工作台或结果区增加：

```text
结论引用
├── 可行性判断引用
├── Pivot 路线引用
├── 工作包引用
└── 轻审核引用
```

每条引用显示：

```text
evidence_id
标题
类型
分数
审核状态
引用角色
引用理由
打开来源链接
移除引用
标为核心
```

---

### 8.2 结论旁边显示证据数量

示例：

```text
可行性：收缩后可做
证据：3 paper / 1 dataset / 1 repo
缺口：dataset license 未确认
```

---

### 8.3 低覆盖率提示

如果 coverage_score < 0.70，前端显示：

```text
当前结论证据覆盖不足，建议补充或复核证据后再生成开题报告。
```

但不要阻断用户继续测试 MVP。

---

### 8.4 Trace 增加用户复核节点

Trace 示例：

```text
系统：为 WP1 绑定 repo_003 作为 baseline 证据
用户：移除 repo_003，原因：只是 demo
系统：重新计算 WP1 证据覆盖率
用户：将 dataset_002 标记为核心证据
系统：可行性判断 coverage_score 从 0.61 提升到 0.78
```

---

## 9. 测试要求

### 9.1 后端单元测试

新增：

```text
apps/api/tests/test_session7_evidence_refs.py
```

必须覆盖：

```text
1. FeasibilitySummary 能绑定 paper/dataset/repo refs
2. rejected evidence 不得作为 supports
3. needs_check evidence 只能作为 warns 或 blocks
4. core evidence 优先被选中
5. PivotRoute 三条路线都有 evidence_refs
6. WorkPackageSuggestion 至少绑定 paper + dataset/repo
7. recommendation_reason 无证据时进入 unsupported_claims
8. LightReview 每个 check 能绑定 evidence_refs
9. refs/rebuild 不改变 review_status
10. refs/coverage 能计算 coverage_score
11. 用户 remove_ref 后 coverage_score 下降
12. 用户 mark_ref_core 后 ref_priority 上升
```

---

### 9.2 前端 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session7_evidence_refs.py
```

必须覆盖：

```text
1. 页面能显示“结论引用”面板
2. 可行性判断旁显示 evidence refs 数量
3. Pivot 路线卡片显示支撑证据
4. 工作包卡片显示 paper/dataset/repo refs
5. 用户可以移除错误引用
6. 移除引用后 coverage 提示更新
7. rejected evidence 不出现在 supports 引用中
8. 点击引用能定位或展开对应证据卡片
```

---

### 9.3 回归测试

必须继续通过：

```text
Session 01 Evidence API
Session 02 Evidence Workbench
Session 03 Human Gates
Session 04 Pivot Routes
Session 05 Evidence Scoring
Session 06 LLM Path
OneTopic happy path
```

如果 Session 06 LLM e2e 存在 flake，Session 07 允许补 mock 模式：

```text
prefer=heuristic
prefer=llm_mock
prefer=auto
```

真实 LLM e2e 不应成为每次 CI 的硬阻断，但必须保留手动 smoke。

---

## 10. 验收标准

Session 07 通过条件：

```text
1. FeasibilitySummary 有 evidence_refs / blocking_refs / confidence
2. 三条 PivotRoute 均有 evidence_refs
3. 每个 WorkPackage 至少有 paper ref，并尽量有 dataset/repo ref
4. ProposalRecommendation 的每条 reason 有证据或被列入 unsupported_claims
5. LightReview 的每个 check 能显示引用证据
6. rejected 证据不会支撑正向结论
7. needs_check 证据只能作为 warning/blocking
8. 前端能展示结论引用面板
9. 用户能移除或替换错误引用
10. Trace 记录用户对引用的复核动作
11. coverage_score < 0.70 时给出补证据提示
12. 新增后端测试和 Playwright 测试通过
```

最低可接受 MVP：

```text
可行性判断 + Pivot 路线 + 工作包 三类结论必须有 evidence_refs；
推荐理由和轻审核可先做部分覆盖，但必须进入 coverage summary。
```

---

## 11. 完工报告要求

完成后新增：

```text
Plan/reports/Session_07_EvidenceRef_验收报告.md
```

报告必须包含：

```text
1. Session 06 遗留 e2e 是否补齐
2. 本阶段范围
3. 新增 / 修改的数据结构
4. 新增 API
5. EvidenceRef 选择规则
6. 前端引用面板变化
7. Trace 变化
8. 覆盖率计算方式
9. 后端测试结果
10. Playwright 测试结果
11. 未做项
12. 下一 Session 建议
```

---

## 12. Session 08 预告

Session 07 完成后，短期目标内的下一步建议是：

```text
Session 08：基于 EvidenceRef 的开题报告 Markdown 导出
```

但 Session 08 仍然不要做完整论文写作，只做开题阶段需要的：

```text
研究背景
研究现状
可行性分析
工作包
创新点
风险预案
答辩追问
证据引用清单
```

每一节必须引用 Session 07 的 evidence_refs。

---

## 13. 一句话执行指令

下一轮不要继续扩大 Agent 能力。

只做：

> 把 Session 05 的证据评分和 Session 06 的 LLM 生成结果全部关进 EvidenceRef 约束里，让可行性、Pivot、工作包和轻审核都能被用户在证据工作台中复核。

